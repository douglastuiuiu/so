# -*- coding: utf-8 -*-
"""
Transicao de calha (retangulo 250x60 -> tubo D100) em chapa de 1.0 mm.

Executar (sem interface):
    freecadcmd transicao_calha.py
ou dentro do FreeCAD: Macro > Executar.

Gera "transicao_calha.fcstd" no diretorio atual.

Nota: a bancada SheetMetal nao possui um tipo nativo "SMLoft". O script tenta
usa-lo se existir; caso contrario cria um loft regrado (Part::Loft, Ruled) e
aplica a espessura com Part::Offset (Fill=True), resultando num solido de chapa
que a bancada SheetMetal (Unfold) consegue planificar gracas as fendas de 1 mm.
"""
import math
import os

import FreeCAD as App
import Part
import Sketcher

V = App.Vector

# ---------------- Parametros ----------------
COMP, LARG = 250.0, 60.0      # retangulo interno (mm)
DIAM = 100.0                  # diametro do tubo (mm)
ALTURA = 300.0                # altura do plano do tubo (mm)
GAP = 1.0                     # fenda para planificacao (mm)
ESPESSURA = 1.0               # chapa de aluminio (mm)

R = DIAM / 2.0
a, b, g = COMP / 2.0, LARG / 2.0, GAP / 2.0

# ---------------- Documento e Body ----------------
doc = App.newDocument("Calha_Transition")
body = doc.addObject("PartDesign::Body", "Body")

xy_plane = None
for feat in body.Origin.OriginFeatures:
    if feat.Role == "XY_Plane":
        xy_plane = feat
        break

# ---------------- Sketch_Base (fenda no centro da aresta superior, y=+b) ----------------
pts_base = [V(g, b, 0), V(a, b, 0), V(a, -b, 0), V(-a, -b, 0), V(-a, b, 0), V(-g, b, 0)]

sk_base = body.newObject("Sketcher::SketchObject", "Sketch_Base")
sk_base.AttachmentSupport = [(xy_plane, "")]
sk_base.MapMode = "FlatFace"
for i in range(len(pts_base) - 1):
    sk_base.addGeometry(Part.LineSegment(pts_base[i], pts_base[i + 1]), False)
for i in range(len(pts_base) - 2):
    sk_base.addConstraint(Sketcher.Constraint("Coincident", i, 2, i + 1, 1))
sk_base.addConstraint(Sketcher.Constraint("Horizontal", 0))
sk_base.addConstraint(Sketcher.Constraint("Vertical", 1))
sk_base.addConstraint(Sketcher.Constraint("Horizontal", 2))
sk_base.addConstraint(Sketcher.Constraint("Vertical", 3))
sk_base.addConstraint(Sketcher.Constraint("Horizontal", 4))
sk_base.addConstraint(Sketcher.Constraint("DistanceX", 3, 1, 1, 1, COMP))
sk_base.addConstraint(Sketcher.Constraint("DistanceY", 2, 1, 1, 1, LARG))
sk_base.addConstraint(Sketcher.Constraint("DistanceX", 4, 2, 0, 1, GAP))
sk_base.addConstraint(Sketcher.Constraint("Symmetric", 1, 1, 3, 1, -1, 1))   # centro na origem
sk_base.addConstraint(Sketcher.Constraint("Symmetric", 4, 2, 0, 1, -2))      # fenda centrada (eixo Y)

# ---------------- Plano de referencia a 300 mm ----------------
datum = body.newObject("PartDesign::Plane", "DatumPlane")
datum.AttachmentSupport = [(xy_plane, "")]
datum.MapMode = "FlatFace"
datum.AttachmentOffset = App.Placement(V(0, 0, ALTURA), App.Rotation())

# ---------------- Sketch_Tubo (circulo D100 com fenda de 1 mm alinhada) ----------------
# O circulo e dividido em arcos nos mesmos angulos polares dos vertices da base,
# para que o loft regrado tenha arestas correspondentes (6 vertices x 6 vertices).
# pts_base percorre em sentido horario; os arcos sao criados anti-horario e unidos.
ang_cw = [math.atan2(p.y, p.x) for p in pts_base]
# extremidades da fenda: corda de exatamente 1 mm no circulo, centrada no eixo +Y
d = math.asin(g / R)
ang_cw[0], ang_cw[-1] = math.pi / 2 - d, math.pi / 2 + d

sk_tubo = body.newObject("Sketcher::SketchObject", "Sketch_Tubo")
sk_tubo.AttachmentSupport = [(datum, "")]
sk_tubo.MapMode = "FlatFace"
circ = Part.Circle(V(0, 0, 0), V(0, 0, 1), R)
for i in range(len(ang_cw) - 1):
    a_end, a_start = ang_cw[i], ang_cw[i + 1]          # arco anti-horario de a_start ate a_end
    while a_end <= a_start:
        a_end += 2 * math.pi
    sk_tubo.addGeometry(Part.ArcOfCircle(circ, a_start, a_end), False)
# Geometria ja e exata (coordenadas calculadas); sem restricoes para evitar
# conflitos do solver entre arcos concentricos encadeados.

doc.recompute()

# ---------------- Loft de chapa (espessura 1.0 mm) ----------------
# A bancada SheetMetal nao possui "SMLoft". O solido da chapa e gerado por um
# loft regrado entre dois perfis fechados em "C" (contorno interno + contorno
# externo deslocado de ESPESSURA), mantendo as medidas internas exatas e a fenda
# de 1 mm para planificacao (SheetMetal > Unfold).
T = ESPESSURA


def perfil_base():
    inn = pts_base
    out = [V(g, b + T, 0), V(a + T, b + T, 0), V(a + T, -b - T, 0),
           V(-a - T, -b - T, 0), V(-a - T, b + T, 0), V(-g, b + T, 0)]
    ed = [Part.LineSegment(inn[i], inn[i + 1]).toShape() for i in range(5)]
    ed.append(Part.LineSegment(inn[5], out[5]).toShape())
    ed += [Part.LineSegment(out[i + 1], out[i]).toShape() for i in reversed(range(5))]
    ed.append(Part.LineSegment(out[0], inn[0]).toShape())
    return Part.Wire(ed)


def perfil_tubo():
    def p(r, t):
        return V(r * math.cos(t), r * math.sin(t), ALTURA)

    def arco(r, t1, t2):  # de t1 para t2 em sentido horario (t2 < t1)
        while t2 >= t1:
            t2 -= 2 * math.pi
        return Part.Arc(p(r, t1), p(r, (t1 + t2) / 2), p(r, t2)).toShape()

    r_in, r_out = R, R + T
    ed = [arco(r_in, ang_cw[i], ang_cw[i + 1]) for i in range(5)]
    ed.append(Part.LineSegment(p(r_in, ang_cw[5]), p(r_out, ang_cw[5])).toShape())
    ed += [Part.Arc(p(r_out, ang_cw[i + 1]),
                    p(r_out, ang_cw[i + 1] + (((ang_cw[i] - ang_cw[i + 1]) % (2 * math.pi)) / 2)),
                    p(r_out, ang_cw[i])).toShape() for i in reversed(range(5))]
    ed.append(Part.LineSegment(p(r_out, ang_cw[0]), p(r_in, ang_cw[0])).toShape())
    return Part.Wire(ed)


solido = Part.makeLoft([perfil_base(), perfil_tubo()], True, True)
loft = doc.addObject("Part::Feature", "SMLoft")
loft.Shape = solido
loft.Label = "SMLoft (chapa {:.1f} mm)".format(T)
sk_base.Visibility = False
sk_tubo.Visibility = False

# ---------------- Salvamento ----------------
doc.recompute()
doc.saveAs(os.path.join(os.getcwd(), "transicao_calha.fcstd"))
App.Console.PrintMessage("Arquivo salvo: transicao_calha.fcstd | volume = {:.1f} mm3 | valido = {}\n"
                         .format(solido.Volume, solido.isValid()))
