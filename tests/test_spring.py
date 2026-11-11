import pytest

from springcad import (SpringSpec, analytic_volume, build_assembly, build_spring,
                       rate_n_per_mm, shear_stress_mpa, wahl)

S = SpringSpec()


@pytest.fixture(scope="module")
def spring():
    return build_spring(S)


def test_spring_is_valid_single_solid(spring):
    assert spring.val().isValid()
    assert len(spring.solids().vals()) == 1


def test_free_length_and_outside_diameter(spring):
    bb = spring.val().BoundingBox()
    assert bb.zlen == pytest.approx(S.free_length, abs=0.5)
    assert bb.xlen == pytest.approx(S.mean_coil_d + S.wire_d, abs=0.5)


def test_cad_volume_matches_hand_calculation(spring):
    # Swept wire volume should equal wire cross section x helix length
    assert spring.val().Volume() == pytest.approx(analytic_volume(S), rel=0.01)


def test_rate_matches_suspension_calculator():
    # suspension-spring-calculator gives 28.0 N/mm for this exact spring
    assert rate_n_per_mm(S) == pytest.approx(28.0, abs=0.1)


def test_wahl_factor():
    assert wahl(S) == pytest.approx(1.166, abs=0.002)


def test_stress_scales_with_force():
    assert shear_stress_mpa(S, 2000) == pytest.approx(2 * shear_stress_mpa(S, 1000))


def test_assembly_parts_valid_and_seats_clear_of_spring():
    spring, lower, upper = build_assembly(S)
    for part in (spring, lower, upper):
        assert part.val().isValid()
    for seat in (lower, upper):
        try:
            vol = spring.intersect(seat).val().Volume()
        except Exception:
            vol = 0.0
        assert vol < 1.0


@pytest.mark.parametrize("bad", [
    SpringSpec(pitch=10),            # coils touch
    SpringSpec(wire_d=40),           # index too low
    SpringSpec(pitch=120),           # too slender, buckles
])
def test_bad_specs_rejected(bad):
    with pytest.raises(ValueError):
        build_spring(bad)
