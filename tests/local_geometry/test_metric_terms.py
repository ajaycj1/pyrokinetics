import pytest
from pyrokinetics import Pyro, template_dir
from pyrokinetics.local_geometry import MetricTerms
import numpy as np
from itertools import product

import sys
import pathlib

docs_dir = pathlib.Path(__file__).parent.parent.parent / "docs"
sys.path.append(str(docs_dir))
from examples import example_JETTO  # noqa

r"""
Tests for metric terms, by comparing results for circular equilibria
with analytic expressions. Equations labelled with reference to
H.G. Dudding's thesis, https://etheses.whiterose.ac.uk/32664/.

Circular expressions:
R = R_0 + r * cos(theta)
Z = r * sin(theta)
dR/dr = cos(theta)
dZ/dr = sin(theta)
"""


def circle_dBzetadr_over_dpsidr(dqdr, q, D, mu0dPdr, r, R0, dpsidr):
    r"""
    Equation 3.139, dividing both sides by dpsi/dr
    Parameters
    ----------
    dqdr - derivative of q w.r.t r
    q - safety factor q
    D -  sqrt(X**2 - 1)
    mu0dPdr - Pressure gradient
    r - Normalised minor radius \rho
    R0 - Normalised major radius R_{maj}
    dpsidr - Derivative of \psi w.r.t \rho

    Returns
    -------
    dB_zeta / dr / (dpsi/dr)
    """

    return (
        dqdr * D / (1 + (q * D) ** 2)
        - (mu0dPdr * (r ** 2) * R0 / (dpsidr ** 2))
        * (q * (D ** 2) / (r * (1 + (q * D) ** 2)))
        - (2 * q / (r * D)) * (1 + (D ** 2)) / (1 + (q * D) ** 2)
    )


def circle_d2alphadrdtheta(dqdr, q, D, mu0dPdr, r, R0, dpsidr, X, theta):
    r"""
    Equation D.93
    Parameters
    ----------
    dqdr - derivative of q w.r.t r
    q - safety factor q
    D -  sqrt(X**2 - 1)
    mu0dPdr - Pressure gradient
    r - Normalised minor radius \rho
    R0 - Normalised major radius R_{maj}
    dpsidr - Derivative of \psi w.r.t \rho
    X - R0 / r (local aspect ratio)
    theta - poloidal angle

    Returns
    -------
    \partial^2 \alpha / \partial \rho \partial \theta
    """
    return (
        dqdr * D / (X + np.cos(theta))
        + (mu0dPdr * (r ** 2) * R0 / (dpsidr ** 2))
        * (q * D / (r * X))
        * (X + np.cos(theta) - X * D / (X + np.cos(theta)))
        - (2 * q * D / r)
        * (
            np.cos(theta) / ((X + np.cos(theta)) ** 2)
            + (1 / D ** 2) / (X + np.cos(theta))
        )
    )


def circle_dalphadr(dqdr, q, D, mu0dPdr, r, R0, dpsidr, X, theta):
    r"""
    Equation D.94

    Parameters
    ----------
    dqdr - derivative of q w.r.t r
    q - safety factor q
    D -  sqrt(X**2 - 1)
    mu0dPdr - Pressure gradient
    r - Normalised minor radius \rho
    R0 - Normalised major radius R_{maj}
    dpsidr - Derivative of \psi w.r.t \rho
    X - R0 / r (local aspect ratio)
    theta - poloidal angle

    Returns
    -------
    \partial \alpha / \partial \rho
    """
    A = 2 * np.arctan(np.sqrt((X - 1) / (X + 1)) * np.tan(theta / 2))
    return (
        dqdr * A
        + (mu0dPdr * (r ** 2) * R0 / (dpsidr ** 2))
        * (q * D / (r * X))
        * (X * theta + np.sin(theta) - X * A)
        - (2 * q / r) * (X / D) * np.sin(theta) / (X + np.cos(theta))
    )


# Test input and outputs of metric terms
def test_metric_terms_input():
    pyro = Pyro(gk_file=template_dir / "input.cgyro", gk_code="CGYRO")
    local_geometry = pyro.local_geometry
    local_species = pyro.local_species
    with pytest.raises(TypeError):
        MetricTerms(local_species)
    metric_terms = MetricTerms(local_geometry)
    assert isinstance(metric_terms, MetricTerms)


# Scan geometry parameters
@pytest.mark.parametrize(
    "q,betaprime,shat",
    [
        *product([1.0, 40.0], [1e-4, 0.1], [0.5, 2.0]),
    ],
)
# Check MetricTerms agrees with analytic results for parameters
def test_alpha_derivatives_for_circle(q, betaprime, shat):
    pyro = Pyro(gk_file=template_dir / "input.cgyro", gk_code="CGYRO")
    local_geometry = pyro.local_geometry
    local_geometry.q = q
    local_geometry.beta_prime = betaprime
    local_geometry.shat = shat

    metric_terms = MetricTerms(local_geometry)

    # load equilibrium parameters
    R0 = local_geometry.Rmaj
    r = local_geometry.rho
    theta = metric_terms.regulartheta
    mu0dPdr = metric_terms.mu0dPdr
    dqdr = metric_terms.dqdr
    dpsidr = metric_terms.dpsidr

    assert np.isclose(metric_terms.q, q)
    assert np.isclose(metric_terms.mu0dPdr, betaprime / 2.0)
    assert np.isclose(metric_terms.dqdr, shat * q / r)

    # geometry quantities
    X = R0 / r
    D = np.sqrt(X ** 2 - 1)

    # test f = (1/dpsidr) * dB_zeta/dr
    analytic_f = circle_dBzetadr_over_dpsidr(dqdr, q, D, mu0dPdr, r, R0, dpsidr)
    data_f = metric_terms.dB_zeta_dr / metric_terms.dpsidr
    assert np.all(np.isclose(analytic_f, data_f, atol=1e-4))

    # test f = d^2 alpha / dr dtheta
    analytic_f = circle_d2alphadrdtheta(dqdr, q, D, mu0dPdr, r, R0, dpsidr, X, theta)
    data_f = metric_terms.d2alpha_drdtheta
    assert np.all(np.isclose(analytic_f, data_f, atol=1e-4))

    # test f = dalpha / dr
    analytic_f = circle_dalphadr(dqdr, q, D, mu0dPdr, r, R0, dpsidr, X, theta)
    data_f = metric_terms.dalpha_dr
    assert np.all(np.isclose(analytic_f, data_f, atol=1e-4))


# Calculate FF_prime using metric terms, and compare to value from
# JETTO
def test_jetto_ffprime(tmp_path):
    pyro = example_JETTO.main(tmp_path / "metric_terms")
    local_geometry = pyro.local_geometry
    metric_terms = MetricTerms(local_geometry)

    # JETTO value
    ffprime = local_geometry.FF_prime
    # Metric Terms calculation
    ffprime_calc = (
        local_geometry.B0
        * metric_terms.dB_zeta_dr
        * metric_terms.B_zeta
        / metric_terms.dpsidr
    )

    # check within 10%
    assert np.isclose(ffprime, ffprime_calc, rtol=1e-1)
