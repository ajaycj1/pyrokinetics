from itertools import product

import numpy as np
from numpy.testing import assert_array_equal, assert_allclose
import matplotlib.pyplot as plt
import pytest

from pyrokinetics.equilibrium import (
    Equilibrium,
    read_equilibrium,
    supported_equilibrium_types,
)
from pyrokinetics import Pyro, template_dir
from pyrokinetics.normalisation import ureg as units

# Test using a known equilibrium, without dependence on any specific file type.
# This is not a valid solution to the Grad-Shafranov equation!


@pytest.fixture(params=[units.m, units.cm])
def circular_equilibrium_args(request):
    len_units = request.param
    psi_units = units.weber / units.rad
    R = np.linspace(1.0, 5.0, 100) * len_units
    Z = np.linspace(-2.0, 2.0, 120) * len_units
    R_norm = (R - 3 * len_units).reshape(100, 1)
    psi_RZ = (np.sqrt(R_norm**2 + Z**2) - 4 * len_units) * psi_units / len_units
    psi_axis = -4.0 * psi_units
    psi_lcfs = -2.0 * psi_units
    a_minor = 2.0 * len_units
    psi = np.linspace(psi_axis, psi_lcfs, 50)
    f = (psi**2) * len_units * units.tesla / psi_units**2
    ff_prime = 2 * psi * f * len_units * units.tesla / psi_units**2
    p = (3000 + 100 * psi / psi_units) * units.pascal
    p_prime = 100 * np.ones(50) * units.pascal / psi_units
    q = np.linspace(0.5, 2.0, 50)
    R_major = 3.0 * np.ones(50) * len_units
    r_minor = np.linspace(0 * len_units, a_minor, 50)
    Z_mid = np.zeros(50) * len_units
    return (
        dict(
            R=R,
            Z=Z,
            psi_RZ=psi_RZ,
            psi=psi,
            f=f,
            ff_prime=ff_prime,
            p=p,
            p_prime=p_prime,
            q=q,
            R_major=R_major,
            r_minor=r_minor,
            Z_mid=Z_mid,
            psi_lcfs=psi_lcfs,
            a_minor=a_minor,
        ),
        len_units,
    )


@pytest.fixture
def circular_equilibrium(circular_equilibrium_args):
    args, len_units = circular_equilibrium_args
    return Equilibrium(**args), len_units


def test_circular_equilibrium_dims(circular_equilibrium):
    eq, len_units = circular_equilibrium
    dims = eq.dims
    assert dims["R_dim"] == 100
    assert dims["Z_dim"] == 120
    assert dims["psi_dim"] == 50


def test_circular_equilibrium_coords(circular_equilibrium):
    eq, len_units = circular_equilibrium
    coords = eq.coords
    # Check dims/shapes
    assert coords["R"].dims == ("R_dim",)
    assert coords["Z"].dims == ("Z_dim",)
    assert coords["psi"].dims == ("psi_dim",)
    assert_array_equal(coords["R"].shape, (100,))
    assert_array_equal(coords["Z"].shape, (120,))
    assert_array_equal(coords["psi"].shape, (50,))
    # Check units
    # Expect meters are used regardless of whether the object was created with cm
    assert coords["R"].data.units == units.m
    assert coords["Z"].data.units == units.m
    assert coords["psi"].data.units == units.weber / units.radian
    # check values
    r_expected = np.linspace(1.0, 5.0, 100)
    z_expected = np.linspace(-2.0, 2.0, 120)
    psi_expected = np.linspace(-4.0, -2.0, 50)
    if len_units == units.cm:
        r_expected /= 100
        z_expected /= 100
    assert_allclose(coords["R"].data.magnitude, r_expected)
    assert_allclose(coords["Z"].data.magnitude, z_expected)
    assert_allclose(coords["psi"].data.magnitude, psi_expected)


def test_circular_equilibrium_data_vars(circular_equilibrium):
    eq, len_units = circular_equilibrium
    data_vars = eq.data_vars
    # Check dims
    assert data_vars["psi_RZ"].dims == ("R_dim", "Z_dim")
    assert data_vars["f"].dims == ("psi_dim",)
    assert data_vars["ff_prime"].dims == ("psi_dim",)
    assert data_vars["p"].dims == ("psi_dim",)
    assert data_vars["p_prime"].dims == ("psi_dim",)
    assert data_vars["q"].dims == ("psi_dim",)
    assert data_vars["R_major"].dims == ("psi_dim",)
    assert data_vars["r_minor"].dims == ("psi_dim",)
    assert data_vars["Z_mid"].dims == ("psi_dim",)
    assert_array_equal(data_vars["psi_RZ"].shape, (100, 120))
    assert_array_equal(data_vars["f"].shape, (50,))
    assert_array_equal(data_vars["ff_prime"].shape, (50,))
    assert_array_equal(data_vars["p"].shape, (50,))
    assert_array_equal(data_vars["p_prime"].shape, (50,))
    assert_array_equal(data_vars["q"].shape, (50,))
    assert_array_equal(data_vars["R_major"].shape, (50,))
    assert_array_equal(data_vars["r_minor"].shape, (50,))
    assert_array_equal(data_vars["Z_mid"].shape, (50,))
    # Check units
    psi_units = units.weber / units.radian
    f_units = units.meter * units.tesla
    assert data_vars["psi_RZ"].data.units == psi_units
    assert data_vars["f"].data.units == f_units
    assert data_vars["ff_prime"].data.units == f_units**2 / psi_units
    assert data_vars["p"].data.units == units.pascal
    assert data_vars["p_prime"].data.units == units.pascal / psi_units
    assert data_vars["q"].data.units == units.dimensionless
    assert data_vars["R_major"].data.units == units.meter
    assert data_vars["r_minor"].data.units == units.meter
    assert data_vars["Z_mid"].data.units == units.meter
    # Check values
    # Only interested in those that could change depending on whether we started with
    # meters or centimeters
    psi = np.linspace(-4.0, -2.0, 50)
    f_expected = psi**2 / (1 if len_units == units.m else 100)
    ff_prime_expected = 2 * psi * f_expected / (1 if len_units == units.m else 100)
    R_major_expected = 3.0 if len_units == units.m else 0.03
    r_minor_expected = np.linspace(0.0, 2.0, 50) / (1 if len_units == units.m else 100)
    assert_allclose(data_vars["f"].data.magnitude, f_expected)
    assert_allclose(data_vars["ff_prime"].data.magnitude, ff_prime_expected)
    assert_allclose(data_vars["R_major"].data.magnitude, R_major_expected)
    assert_allclose(data_vars["r_minor"].data.magnitude, r_minor_expected)


def test_circular_equilibrium_attrs(circular_equilibrium):
    eq, len_units = circular_equilibrium
    # Check units
    assert eq.R_axis.units == units.m
    assert eq.Z_axis.units == units.m
    assert eq.psi_axis.units == units.weber / units.radian
    assert eq.psi_lcfs.units == units.weber / units.radian
    assert eq.a_minor.units == units.m
    assert eq.dR.units == units.m
    assert eq.dZ.units == units.m
    # Check values
    assert np.isclose(eq.R_axis.magnitude, 3.0 if len_units == units.m else 0.03)
    assert np.isclose(eq.Z_axis.magnitude, 0.0)
    assert np.isclose(eq.psi_axis.magnitude, -4.0)
    assert np.isclose(eq.psi_lcfs.magnitude, -2.0)
    assert np.isclose(eq.a_minor.magnitude, 2.0 if len_units == units.m else 0.02)
    assert np.isclose(eq.dR.magnitude, (4.0 if len_units == units.m else 0.04) / 99)
    assert np.isclose(eq.dZ.magnitude, (4.0 if len_units == units.m else 0.04) / 119)
    assert eq.eq_type == "None"


@pytest.mark.parametrize(
    "key",
    [
        "R",
        "Z",
        "psi_RZ",
        "psi",
        "f",
        "ff_prime",
        "p",
        "p_prime",
        "q",
        "R_major",
        "r_minor",
        "Z_mid",
        "psi_lcfs",
        "a_minor",
    ],
)
def test_circular_equilibrium_bad_units(circular_equilibrium_args, key):
    """Test to ensure Equilibrium raises an exception when given incorrect units"""
    args, len_units = circular_equilibrium_args
    args[key] *= units.second
    with pytest.raises(Exception):
        Equilibrium(**args)


def test_circular_equilibrium_flux_surface(circular_equilibrium):
    eq, len_units = circular_equilibrium
    fs = eq.flux_surface(0.5)
    radius = np.hypot(fs["R"] - fs.R_major, fs["Z"]).data.magnitude
    expected = np.ones(len(fs["R"])) / (1 if len_units == units.m else 100)
    assert_allclose(radius, expected, rtol=1e-4, atol=1e-4)


def test_circular_equilibrium_psi(circular_equilibrium):
    eq, len_units = circular_equilibrium
    psi_units = units.weber / units.radian
    assert eq.psi(0.5).units == psi_units
    assert np.isclose(eq.psi(0.0), -4.0 * psi_units)
    assert np.isclose(eq.psi(0.5), -3.0 * psi_units)
    assert np.isclose(eq.psi(1.0), -2.0 * psi_units)


def test_circular_equilibrium_psi_n(circular_equilibrium):
    eq, len_units = circular_equilibrium
    assert eq.psi_n(-2.0).units == units.dimensionless
    assert np.isclose(eq.psi_n(-4.0), 0.0)
    assert np.isclose(eq.psi_n(-3.0), 0.5)
    assert np.isclose(eq.psi_n(-2.0), 1.0)


def test_circular_equilibrium_rho(circular_equilibrium):
    eq, len_units = circular_equilibrium
    assert eq.rho(0.5).units == units.dimensionless
    assert np.isclose(eq.rho(0.0), 0.0)
    assert np.isclose(eq.rho(0.5), 0.5)
    assert np.isclose(eq.rho(1.0), 1.0)


def test_circular_equilibrium_f(circular_equilibrium):
    eq, len_units = circular_equilibrium
    f_units = units.m * units.tesla
    factor = 1.0 if len_units == units.meter else 0.01
    assert eq.f(0.5).units == f_units
    assert np.isclose(eq.f(0.0), 16.0 * factor * f_units)
    assert np.isclose(eq.f(0.5), 9.0 * factor * f_units)
    assert np.isclose(eq.f(1.0), 4.0 * factor * f_units)


def test_circular_equilibrium_f_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    f_units = units.m * units.tesla
    psi_units = units.weber / units.radian
    factor = 1.0 if len_units == units.meter else 0.01
    assert eq.f_prime(0.5).units == f_units / psi_units
    assert np.isclose(eq.f_prime(0.0), -8.0 * factor * f_units / psi_units)
    assert np.isclose(eq.f_prime(0.5), -6.0 * factor * f_units / psi_units)
    assert np.isclose(eq.f_prime(1.0), -4.0 * factor * f_units / psi_units)


def test_circular_equilibrium_ff_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    f_units = units.m * units.tesla
    psi_units = units.weber / units.radian
    factor = 1.0 if len_units == units.meter else 0.0001
    assert eq.ff_prime(0.5).units == f_units**2 / psi_units
    assert np.isclose(eq.ff_prime(0.0), -8.0 * 16.0 * factor * f_units**2 / psi_units)
    assert np.isclose(eq.ff_prime(0.5), -6.0 * 9.0 * factor * f_units**2 / psi_units)
    assert np.isclose(eq.ff_prime(1.0), -4.0 * 4.0 * factor * f_units**2 / psi_units)


def test_circular_equilibrium_p(circular_equilibrium):
    eq, len_units = circular_equilibrium

    def p_expected(x):
        return (2600 + x * 200) * units.pascal

    assert eq.p(0.5).units == units.pascal
    assert np.isclose(eq.p(0.0), p_expected(0.0))
    assert np.isclose(eq.p(0.5), p_expected(0.5))
    assert np.isclose(eq.p(1.0), p_expected(1.0))


def test_circular_equilibrium_p_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    psi_units = units.weber / units.radian
    assert eq.p_prime(0.5).units == units.pascal / psi_units
    assert np.isclose(eq.p_prime(0.0), 100 * units.pascal / psi_units)
    assert np.isclose(eq.p_prime(0.5), 100 * units.pascal / psi_units)
    assert np.isclose(eq.p_prime(1.0), 100 * units.pascal / psi_units)


def test_circular_equilibrium_q(circular_equilibrium):
    eq, len_units = circular_equilibrium
    assert eq.q(0.5).units == units.dimensionless
    assert np.isclose(eq.q(0.0), 0.5)
    assert np.isclose(eq.q(0.5), 1.25)
    assert np.isclose(eq.q(1.0), 2.0)


def test_circular_equilibrium_q_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    psi_units = units.weber / units.radian
    assert eq.q_prime(0.5).units == psi_units**-1
    assert np.isclose(eq.q_prime(0.0), 0.75 / psi_units)
    assert np.isclose(eq.q_prime(0.5), 0.75 / psi_units)
    assert np.isclose(eq.q_prime(1.0), 0.75 / psi_units)


def test_circular_equilibrium_R_major(circular_equilibrium):
    eq, len_units = circular_equilibrium
    factor = 1.0 if len_units == units.m else 0.01
    assert eq.R_major(0.5).units == units.m
    assert np.isclose(eq.R_major(0.0), 3.0 * factor * units.m)
    assert np.isclose(eq.R_major(0.5), 3.0 * factor * units.m)
    assert np.isclose(eq.R_major(1.0), 3.0 * factor * units.m)


def test_circular_equilibrium_R_major_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    psi_units = units.weber / units.radian
    assert eq.R_major_prime(0.5).units == units.m / psi_units
    assert np.isclose(eq.R_major_prime(0.0), 0.0 * units.m / psi_units)
    assert np.isclose(eq.R_major_prime(0.5), 0.0 * units.m / psi_units)
    assert np.isclose(eq.R_major_prime(1.0), 0.0 * units.m / psi_units)


def test_circular_equilibrium_r_minor(circular_equilibrium):
    eq, len_units = circular_equilibrium
    factor = 1.0 if len_units == units.m else 0.01
    assert eq.r_minor(0.5).units == units.m
    assert np.isclose(eq.r_minor(0.0), 0.0 * factor * units.m)
    assert np.isclose(eq.r_minor(0.5), 1.0 * factor * units.m)
    assert np.isclose(eq.r_minor(1.0), 2.0 * factor * units.m)


def test_circular_equilibrium_r_minor_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    psi_units = units.weber / units.radian
    factor = 1.0 if len_units == units.m else 0.01
    assert eq.r_minor_prime(0.5).units == units.m / psi_units
    assert np.isclose(eq.r_minor_prime(0.0), 1.0 * factor * units.m / psi_units)
    assert np.isclose(eq.r_minor_prime(0.5), 1.0 * factor * units.m / psi_units)
    assert np.isclose(eq.r_minor_prime(1.0), 1.0 * factor * units.m / psi_units)


def test_circular_equilibrium_Z_mid(circular_equilibrium):
    eq, len_units = circular_equilibrium
    assert eq.Z_mid(0.5).units == units.m
    assert np.isclose(eq.Z_mid(0.0), 0.0 * units.m)
    assert np.isclose(eq.Z_mid(0.5), 0.0 * units.m)
    assert np.isclose(eq.Z_mid(1.0), 0.0 * units.m)


def test_circular_equilibrium_Z_mid_prime(circular_equilibrium):
    eq, len_units = circular_equilibrium
    psi_units = units.weber / units.radian
    assert eq.Z_mid_prime(0.5).units == units.m / psi_units
    assert np.isclose(eq.Z_mid_prime(0.0), 0.0 * units.m / psi_units)
    assert np.isclose(eq.Z_mid_prime(0.5), 0.0 * units.m / psi_units)
    assert np.isclose(eq.Z_mid_prime(1.0), 0.0 * units.m / psi_units)


@pytest.mark.parametrize(
    "quantity,normalised",
    product(
        [
            "f",
            "ff_prime",
            "p",
            "p_prime",
            "q",
            "R_major",
            "r_minor",
            "Z_mid",
        ],
        [True, False],
    ),
)
def test_circular_equilibrium_plot(circular_equilibrium, quantity, normalised):
    eq = circular_equilibrium[0]
    psi = eq["psi_n" if normalised else "psi"]
    # Test plot with no provided axes, provide kwargs
    ax = eq.plot(quantity, psi_n=normalised, label="plot 1")
    # Plot again on same ax with new label
    ax = eq.plot(quantity, ax=ax, psi_n=normalised, label="plot_2")
    # Test correct labels
    assert psi.long_name in ax.get_xlabel()
    assert eq[quantity].long_name in ax.get_ylabel()
    # Ensure the correct data is plotted
    for line in ax.lines:
        assert_allclose(line.get_xdata(), psi.data.magnitude)
        assert_allclose(line.get_ydata(), eq[quantity].data.magnitude)
    # Remove figure so it doesn't sit around in memory
    plt.close(ax.get_figure())


def test_circular_equilibrium_plot_bad_quantity(circular_equilibrium):
    eq = circular_equilibrium[0]
    with pytest.raises(ValueError):
        eq.plot("hello world")


def test_circular_equilibrium_plot_quantity_on_wrong_grid(circular_equilibrium):
    eq = circular_equilibrium[0]
    with pytest.raises(ValueError):
        eq.plot("psi_RZ")


def test_circular_equilibrium_plot_contour(circular_equilibrium):
    eq = circular_equilibrium[0]
    # Test plot with no provided axes, provide kwargs
    ax = eq.contour(levels=50)
    # Plot again on same ax
    ax = eq.contour(ax=ax)
    # Test correct labels
    assert eq["R"].long_name in ax.get_xlabel()
    assert eq["Z"].long_name in ax.get_ylabel()
    # Remove figure so it doesn't sit around in memory
    plt.close(ax.get_figure())


@pytest.mark.parametrize(
    "quantity",
    [
        "R",
        "Z",
        "b_poloidal",
    ],
)
def test_circular_equilibrium_flux_surface_plot(circular_equilibrium, quantity):
    eq = circular_equilibrium[0]
    fs = eq.flux_surface(0.5)
    # Test plot with no provided axes, provide kwargs
    ax = fs.plot(quantity, label="plot 1")
    # Plot again on same ax with new label
    ax = fs.plot(quantity, ax=ax, label="plot_2")
    # Test correct labels
    assert fs["theta"].long_name in ax.get_xlabel()
    assert fs[quantity].long_name in ax.get_ylabel()
    # Ensure the correct data is plotted
    for line in ax.lines:
        assert_allclose(line.get_xdata(), fs["theta"].data.magnitude)
        assert_allclose(line.get_ydata(), fs[quantity].data.magnitude)
    # Remove figure so it doesn't sit around in memory
    plt.close(ax.get_figure())


def test_circular_equilibrium_flux_surface_plot_bad_quantity(circular_equilibrium):
    eq = circular_equilibrium[0]
    fs = eq.flux_surface(0.7)
    with pytest.raises(ValueError):
        fs.plot("hello world")


def test_circular_equilibrium_flux_surface_plot_path(circular_equilibrium):
    eq = circular_equilibrium[0]
    fs = eq.flux_surface(0.5)
    # Test plot with no provided axes, provide kwargs
    ax = fs.plot_path(label="plot 1")
    # Plot again on same ax with new label
    ax = fs.plot_path(ax=ax, label="plot_2")
    # Test correct labels
    assert fs["R"].long_name in ax.get_xlabel()
    assert fs["Z"].long_name in ax.get_ylabel()
    # Ensure the correct data is plotted
    for line in ax.lines:
        assert_allclose(line.get_xdata(), fs["R"].data.magnitude)
        assert_allclose(line.get_ydata(), fs["Z"].data.magnitude)


def test_circular_equilibrium_netcdf_round_trip(tmp_path, circular_equilibrium):
    eq = circular_equilibrium[0]
    dir_ = tmp_path / "circular_equilibrium_netcdf_round_trip"
    dir_.mkdir()
    file_ = dir_ / "my_netcdf.nc"
    eq.to_netcdf(file_)
    eq2 = read_equilibrium(file_)
    # Test coords
    for k, v in eq.coords.items():
        assert k in eq2.coords
        assert_allclose(v.data.magnitude, eq2[k].data.magnitude)
        assert v.data.units == eq2[k].data.units
    # Test data vars
    for k, v in eq.data_vars.items():
        assert k in eq2.data_vars
        assert_allclose(v.data.magnitude, eq2[k].data.magnitude)
        assert v.data.units == eq2[k].data.units
    # Test attributes
    for k, v in eq.attrs.items():
        if hasattr(v, "magnitude"):
            assert np.isclose(v, eq2.attrs[k])
            assert getattr(eq, k).units == getattr(eq2, k).units
        else:
            assert v == eq2.attrs[k]


# The following tests use 'golden answers', and depend on template files.
# They may fail if algorithms are updated such that the end results aren't accurate to
# within 1e-5 relative error.


@pytest.fixture(scope="module")
def geqdsk_equilibrium():
    return read_equilibrium(template_dir / "test.geqdsk", eq_type="GEQDSK")


@pytest.fixture(scope="module")
def transp_cdf_equilibrium():
    return read_equilibrium(template_dir / "transp_eq.cdf", eq_type="TRANSP", time=0.2)


@pytest.fixture(scope="module")
def transp_gq_equilibrium():
    return read_equilibrium(template_dir / "transp_eq.geqdsk", eq_type="GEQDSK")


def test_read_geqdsk(geqdsk_equilibrium):
    eq = geqdsk_equilibrium

    assert len(eq["R"]) == 69
    assert len(eq["Z"]) == 175
    assert eq["psi_RZ"].shape[0] == 69
    assert eq["psi_RZ"].shape[1] == 175
    assert len(eq["psi"]) == 69
    assert len(eq["f"]) == 69
    assert len(eq["p"]) == 69
    assert len(eq["q"]) == 69
    assert len(eq["ff_prime"]) == 69
    assert len(eq["p_prime"]) == 69
    assert len(eq["R_major"]) == 69
    assert len(eq["r_minor"]) == 69
    assert len(eq["Z_mid"]) == 69


def test_get_flux_surface(geqdsk_equilibrium):
    fs = geqdsk_equilibrium.flux_surface(0.5)
    assert np.isclose(min(fs["R"].data), 1.747667428494825 * units.m)
    assert np.isclose(max(fs["R"].data), 3.8021621078549717 * units.m)
    assert np.isclose(min(fs["Z"].data), -3.112902507930995 * units.m)
    assert np.isclose(max(fs["Z"].data), 3.112770914245634 * units.m)


def test_get_lcfs(geqdsk_equilibrium):
    lcfs = geqdsk_equilibrium.flux_surface(1.0)
    assert np.isclose(min(lcfs["R"].data), 1.0 * units.m)
    assert np.isclose(max(lcfs["R"].data), 4.0001495 * units.m)
    assert np.isclose(min(lcfs["Z"].data), -4.19975 * units.m)
    assert np.isclose(max(lcfs["Z"].data), 4.19975 * units.m)


def test_b_radial(geqdsk_equilibrium):
    assert np.isclose(geqdsk_equilibrium.b_radial(2.3, 3.1), -0.321247509 * units.tesla)
    assert np.isclose(
        geqdsk_equilibrium.b_radial(3.8, 0.0), -6.101095916e-06 * units.tesla
    )


def test_b_vertical(geqdsk_equilibrium):
    assert np.isclose(
        geqdsk_equilibrium.b_vertical(2.3, 3.1), -0.026254786738 * units.tesla
    )
    assert np.isclose(
        geqdsk_equilibrium.b_vertical(3.8, 0.0), 1.1586967264 * units.tesla
    )


def test_b_poloidal(geqdsk_equilibrium):
    assert np.isclose(
        geqdsk_equilibrium.b_poloidal(2.3, 3.1), 0.3223185944 * units.tesla
    )
    assert np.isclose(
        geqdsk_equilibrium.b_poloidal(3.8, 0.0), 1.1586967264 * units.tesla
    )


def test_b_toroidal(geqdsk_equilibrium):
    assert np.isclose(
        geqdsk_equilibrium.b_toroidal(2.3, 3.1), 2.6499210636 * units.tesla
    )
    assert np.isclose(
        geqdsk_equilibrium.b_toroidal(3.8, 0.0), 1.6038789003 * units.tesla
    )


def assert_within_ten_percent(key, cdf_value, gq_value):

    difference = np.abs((cdf_value - gq_value))
    smallest_value = np.min(np.abs([cdf_value, gq_value]))

    if smallest_value == 0.0:
        if difference == 0.0:
            assert True
        else:
            assert (
                np.abs((cdf_value - gq_value) / np.min(np.abs([cdf_value, gq_value])))
                < 0.1
            ), f"{key} not within 10 percent"
    else:
        assert difference / smallest_value < 0.5, f"{key} not within 10 percent"


def test_compare_transp_cdf_geqdsk(transp_cdf_equilibrium, transp_gq_equilibrium):
    psi_surface = 0.5

    # Load up pyro object and generate local Miller parameters at psi_n=0.5
    # FIXME Pyro should read eq file, should not be inserting it manually
    pyro_gq = Pyro()
    pyro_gq.eq = transp_gq_equilibrium
    pyro_gq.load_local_geometry(psi_n=psi_surface, local_geometry="Miller")

    # Load up pyro object
    pyro_cdf = Pyro()
    pyro_cdf.eq = transp_cdf_equilibrium
    pyro_cdf.load_local_geometry(psi_n=psi_surface, local_geometry="Miller")

    ignored_geometry_attrs = [
        "B0",
        "psi_n",
        "r_minor",
        "a_minor",
        "f_psi",
        "R",
        "Z",
        "theta",
        "b_poloidal",
        "R_eq",
        "Z_eq",
        "theta_eq",
        "b_poloidal_eq",
        "dRdtheta",
        "dZdtheta",
        "dRdr",
        "dZdr",
        "dpsidr",
        "pressure",
        "dpressure_drho",
        "Z0",
        "local_geometry",
    ]

    for key in pyro_gq.local_geometry.keys():
        if key in ignored_geometry_attrs:
            continue
        assert_within_ten_percent(
            key, pyro_cdf.local_geometry[key], pyro_gq.local_geometry[key]
        )


@pytest.mark.parametrize(
    "filename, eq_type",
    [
        ("transp_eq.cdf", "TRANSP"),
        ("transp_eq.geqdsk", "GEQDSK"),
        ("test.geqdsk", "GEQDSK"),
    ],
)
def test_filetype_inference(filename, eq_type):
    eq = read_equilibrium(template_dir / filename)
    assert eq.eq_type == eq_type


def test_supported_equilibrium_types():
    eq_types = supported_equilibrium_types()
    assert "GEQDSK" in eq_types
    assert "TRANSP" in eq_types
    assert "Pyrokinetics" in eq_types