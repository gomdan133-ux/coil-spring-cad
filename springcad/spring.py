"""Parametric helical compression spring (plain ends) with spring seats.

All dimensions in millimeters, forces in N, stresses in MPa.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cadquery as cq

G_STEEL_MPA = 79_300.0       # shear modulus of spring steel
RHO_STEEL = 7850.0           # kg/m^3


@dataclass
class SpringSpec:
    wire_d: float = 12.5
    mean_coil_d: float = 110.0
    active_coils: float = 6.5
    pitch: float = 45.0              # distance between coil centers along the axis
    seat_od: float = 140.0
    seat_id: float = 70.0
    seat_t: float = 6.0
    seat_lip_h: float = 8.0          # centering lip inside the coil

    @property
    def free_length(self) -> float:
        return self.active_coils * self.pitch + self.wire_d

    @property
    def solid_height(self) -> float:
        return (self.active_coils + 1) * self.wire_d

    @property
    def index(self) -> float:
        return self.mean_coil_d / self.wire_d

    def check(self) -> None:
        if not 4 <= self.index <= 16:
            raise ValueError(f"spring index {self.index:.1f} outside the practical 4 to 16 range")
        if self.pitch <= self.wire_d:
            raise ValueError("pitch must be larger than wire diameter or the coils touch")
        if self.free_length / self.mean_coil_d > 5.2:
            raise ValueError("spring is too slender and would buckle")
        if self.seat_id >= self.mean_coil_d - self.wire_d:
            raise ValueError("seat lip must fit inside the coil")


# ---------- engineering checks (hand calculations) ----------

def rate_n_per_mm(s: SpringSpec) -> float:
    """k = G d^4 / (8 D^3 Na)"""
    return G_STEEL_MPA * s.wire_d ** 4 / (8 * s.mean_coil_d ** 3 * s.active_coils)


def wahl(s: SpringSpec) -> float:
    c = s.index
    return (4 * c - 1) / (4 * c - 4) + 0.615 / c


def shear_stress_mpa(s: SpringSpec, force_n: float) -> float:
    """tau = Kw * 8 F D / (pi d^3)"""
    return wahl(s) * 8 * force_n * s.mean_coil_d / (math.pi * s.wire_d ** 3)


def wire_length(s: SpringSpec) -> float:
    return s.active_coils * math.hypot(math.pi * s.mean_coil_d, s.pitch)


def analytic_volume(s: SpringSpec) -> float:
    return math.pi * s.wire_d ** 2 / 4 * wire_length(s)


# ---------- CAD ----------

def build_spring(spec: SpringSpec | None = None) -> cq.Workplane:
    """Swept circular wire along a helix; axis on Z, starting at Z = wire_d / 2."""
    s = spec or SpringSpec()
    s.check()
    r = s.mean_coil_d / 2
    helix = cq.Wire.makeHelix(pitch=s.pitch, height=s.active_coils * s.pitch, radius=r)
    # Profile circle at the helix start, tilted to the helix angle so it is normal to the path
    lead_angle = math.degrees(math.atan2(s.pitch, math.pi * s.mean_coil_d))
    profile = (cq.Workplane("XZ").center(r, 0)
               .transformed(rotate=(lead_angle, 0, 0)).circle(s.wire_d / 2))
    spring = profile.sweep(cq.Workplane().add(helix), isFrenet=True)
    return spring.translate((0, 0, s.wire_d / 2))


def build_seat(s: SpringSpec, top: bool = False) -> cq.Workplane:
    """Flat spring seat (perch) with a centering lip that sits inside the coil."""
    seat = (cq.Workplane("XY").circle(s.seat_od / 2).circle(s.seat_id / 2).extrude(s.seat_t))
    lip = (cq.Workplane("XY").workplane(offset=s.seat_t)
           .circle(s.mean_coil_d / 2 - s.wire_d / 2 - 1.0).circle(s.seat_id / 2)
           .extrude(s.seat_lip_h))
    seat = seat.union(lip).edges(">Z").fillet(1.0)
    if top:
        seat = seat.mirror("XY").translate((0, 0, s.free_length + 2 * s.seat_t))
    return seat


def build_assembly(s: SpringSpec | None = None):
    s = s or SpringSpec()
    spring = build_spring(s).translate((0, 0, s.seat_t))
    return spring, build_seat(s), build_seat(s, top=True)
