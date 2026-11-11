"""Build the spring and seats; export STEP, STL, SVG, PNG and a spring data report.

Run from the repo root:  python scripts/build_all.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cadquery as cq  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

from springcad import (RHO_STEEL, SpringSpec, analytic_volume, build_assembly,  # noqa: E402
                       rate_n_per_mm, shear_stress_mpa, wahl, wire_length)

OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)


def render_png(parts, path, colors, elev=12, azim=-60):
    fig = plt.figure(figsize=(5, 7), dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    light = np.array([0.4, -0.6, 0.7])
    light /= np.linalg.norm(light)
    allpts = []
    for part, base in zip(parts, colors):
        verts, tris = part.val().tessellate(0.2, 0.2)
        pts = np.array([(v.x, v.y, v.z) for v in verts])
        faces = pts[np.array(tris)]
        n = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        shade = 0.35 + 0.65 * np.abs(n @ light)
        ax.add_collection3d(Poly3DCollection(faces, facecolors=np.clip(np.outer(shade, base), 0, 1),
                                             edgecolor="none"))
        allpts.append(pts)
    pts = np.vstack(allpts)
    c = (pts.max(0) + pts.min(0)) / 2
    span = (pts.max(0) - pts.min(0)).max() / 2
    for setter, ci in zip((ax.set_xlim, ax.set_ylim, ax.set_zlim), c):
        setter(ci - span, ci + span)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main():
    s = SpringSpec()
    spring, lower, upper = build_assembly(s)
    cq.exporters.export(spring, str(OUT / "coil_spring.step"))
    cq.exporters.export(lower, str(OUT / "spring_seat.step"))
    cq.exporters.export(spring.add(lower).add(upper), str(OUT / "spring_assembly.step"))
    cq.exporters.export(spring, str(OUT / "coil_spring.stl"), tolerance=0.1, angularTolerance=0.2)
    cq.exporters.export(spring.union(lower).union(upper), str(OUT / "spring_assembly_front.svg"), opt={
        "projectionDir": (0, -1, 0), "showHidden": False, "width": 400, "height": 700, "strokeWidth": 0.3})
    render_png([spring, lower, upper], OUT / "spring_assembly.png",
               [(0.78, 0.25, 0.22), (0.55, 0.58, 0.62), (0.55, 0.58, 0.62)])

    k = rate_n_per_mm(s)
    ride_load = 4336.0   # N, front corner at ride height (from suspension-spring-calculator example)
    ride_defl = ride_load / k
    travel_to_solid = s.free_length - s.solid_height
    solid_load = k * travel_to_solid
    cad_vol = spring.val().Volume()
    report = {
        "spec": s.__dict__,
        "free_length_mm": s.free_length,
        "solid_height_mm": s.solid_height,
        "spring_index": round(s.index, 2),
        "wahl_factor": round(wahl(s), 3),
        "rate_n_per_mm": round(k, 2),
        "wire_length_mm": round(wire_length(s), 1),
        "cad_volume_mm3": round(cad_vol, 1),
        "hand_calc_volume_mm3": round(analytic_volume(s), 1),
        "volume_error_pct": round((cad_vol / analytic_volume(s) - 1) * 100, 6),
        "mass_kg": round(cad_vol * 1e-9 * RHO_STEEL, 3),
        "ride_height": {"load_n": ride_load, "deflection_mm": round(ride_defl, 1),
                        "length_mm": round(s.free_length - ride_defl, 1),
                        "shear_stress_mpa": round(shear_stress_mpa(s, ride_load))},
        "at_solid": {"load_n": round(solid_load), "travel_mm": round(travel_to_solid, 1),
                     "shear_stress_mpa": round(shear_stress_mpa(s, solid_load))},
    }
    (OUT / "spring_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k2: v for k2, v in report.items() if k2 != "spec"}, indent=2))


if __name__ == "__main__":
    main()
