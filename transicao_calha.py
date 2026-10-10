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

# ---------------- Loft de chapa ----------------
loft = None
try:
    import SheetMetal  # noqa: F401  (verifica bancada instalada)
    try:
        loft = doc.addObject("SheetMetal::SMLoft", "SMLoft")
        loft.Sections = [sk_base, sk_tubo]
        loft.Thickness = ESPESSURA
    except Exception:
        if loft is not None:
            doc.removeObject(loft.Name)
        loft = None
except ImportError:
    pass

if loft is None:
    superficie = doc.addObject("Part::Loft", "Loft_Superficie")
    superficie.Sections = [sk_base, sk_tubo]
    superficie.Solid = False
    superficie.Ruled = True
    superficie.Closed = False

    loft = doc.addObject("Part::Offset", "SMLoft")       # chapa com espessura
    loft.Source = superficie
    loft.Value = ESPESSURA                                 # para fora: medidas internas preservadas
    loft.Mode = "Skin"
    loft.Join = "Intersection"
    loft.Fill = True
    superficie.Visibility = False

# ---------------- Salvamento ----------------
doc.recompute()
doc.saveAs(os.path.join(os.getcwd(), "transicao_calha.fcstd"))
App.Console.PrintMessage("Arquivo salvo: transicao_calha.fcstd\n")
