import numpy as np
from typing import Tuple
from scipy.optimize import least_squares  # type: ignore
from scipy.integrate import simpson
from .local_geometry import LocalGeometry
from ..typing import ArrayLike
from .local_geometry import default_inputs


def default_mxh_inputs():
    # Return default args to build a LocalGeometryMXH
    # Uses a function call to avoid the user modifying these values

    n_moments = 4
    base_defaults = default_inputs()
    mxh_defaults = {
        "cn": np.zeros(n_moments),
        "dcndr": np.zeros(n_moments),
        "sn": np.zeros(n_moments),
        "dsndr": np.zeros(n_moments),
        "local_geometry": "MXH",
    }

    return {**base_defaults, **mxh_defaults}


class LocalGeometryMXH(LocalGeometry):
    r"""Local equilibrium representation defined as in: `PPCF 63 (2021) 012001
    (5pp) <https://doi.org/10.1088/1361-6587/abc63b>`_

    Miller eXtended Harmonic (MXH)

    .. math::
        \begin{align}
        R(r, \theta) &= R_{major}(r) + r \cos(\theta_R) \\
        Z(r, \theta) &= Z_0(r) + r \kappa(r) \sin(\theta) \\
        \theta_R &= \theta + c_0(r) + \sum_{n=1}^N [c_n(r) \cos(n \theta) + s_n(r) \sin(n \theta)] \\
        r &= (\max(R) - \min(R)) / 2
        \end{align}

    Data stored in a ordered dictionary

    Attributes
    ----------
    psi_n : Float
        Normalised Psi
    rho : Float
        r/a
    r_minor : Float
        Minor radius of flux surface
    a_minor : Float
        Minor radius of LCFS [m]
    Rmaj : Float
        Normalised Major radius (Rmajor/a_minor)
    Z0 : Float
        Normalised vertical position of midpoint (Zmid / a_minor)
    f_psi : Float
        Torodial field function
    B0 : Float
        Toroidal field at major radius (Fpsi / Rmajor) [T]
    bunit_over_b0 : Float
        Ratio of GACODE normalising field = :math:`q/r \partial \psi/\partial r` [T] to B0
    dpsidr : Float
        :math:`\frac{\partial \psi}{\partial r}`
    q : Float
        Safety factor
    shat : Float
        Magnetic shear :math:`r/q \partial q/ \partial r`
    beta_prime : Float
        :math:`\beta = 2 \mu_0 \partial p \partial \rho 1/B0^2`

    kappa : Float
        Elongation
    s_kappa : Float
        Shear in Elongation :math:`r/\kappa \partial \kappa/\partial r`
    shift : Float
        Shafranov shift
    dZ0dr : Float
        Shear in midplane elevation
    thetaR : ArrayLike
        thetaR values at theta
    dthetaR_dtheta : ArrayLike
        Derivative of thetaR w.r.t theta at theta
    dthetaR_dr : ArrayLike
        Derivative of thetaR w.r.t r at theta
    cn : ArrayLike
        cosine moments of thetaR
    sn : ArrayLike
        sine moments of thetaR
    dcndr : ArrayLike
        Shear in cosine moments :math:`\partial c_n/\partial r`
    dsndr : ArrayLike
        Shear in sine moments :math:`\partial s_n/\partial r`

    R_eq : Array
        Equilibrium R data used for fitting
    Z_eq : Array
        Equilibrium Z data used for fitting
    b_poloidal_eq : Array
        Equilibrium B_poloidal data used for fitting
    theta_eq : Float
        theta values for equilibrium data

    R : Array
        Fitted R data
    Z : Array
        Fitted Z data
    b_poloidal : Array
        Fitted B_poloidal data
    theta : Float
        Fitted theta data

    dRdtheta : Array
        Derivative of fitted :math:`R` w.r.t :math:`\theta`
    dRdr : Array
        Derivative of fitted :math:`R` w.r.t :math:`r`
    dZdtheta : Array
        Derivative of fitted :math:`Z` w.r.t :math:`\theta`
    dZdr : Array
        Derivative of fitted :math:`Z` w.r.t :math:`r`

    d2Rdtheta2 : Array
        Second derivative of fitted :math:`R` w.r.t :math:`\theta`
    d2Rdrdtheta : Array
        Derivative of fitted :math:`R` w.r.t :math:`r` and :math:`\theta`
    d2Zdtheta2 : Array
        Second derivative of fitted :math:`Z` w.r.t :math:`\theta`
    d2Zdrdtheta : Array
        Derivative of fitted :math:`Z` w.r.t :math:`r` and :math:`\theta`

    """

    def __init__(self, *args, **kwargs):
        s_args = list(args)

        if (
            args
            and not isinstance(args[0], LocalGeometryMXH)
            and isinstance(args[0], dict)
        ):
            super().__init__(*s_args, **kwargs)

        elif len(args) == 0:
            self.default()

    def _set_shape_coefficients(self, R, Z, b_poloidal, verbose=False, shift=0.0):
        r"""
        Calculates MXH shaping coefficients from R, Z and b_poloidal

        Parameters
        ----------
        R : Array
            R for the given flux surface
        Z : Array
            Z for the given flux surface
        b_poloidal : Array
            :math:`b_\theta` for the given flux surface
        verbose : Boolean
            Controls verbosity
        shift : Float
            Initial guess for shafranov shift
        """

        kappa = (max(Z) - min(Z)) / (2 * self.r_minor)

        Zmid = (max(Z) + min(Z)) / 2

        Zind = np.argmax(abs(Z))

        R_upper = R[Zind]

        normalised_height = (Z - Zmid) / (kappa * self.r_minor)

        # Floating point error can lead to >|1.0|
        normalised_height = np.where(
            np.isclose(normalised_height, 1.0), 1.0, normalised_height
        )
        normalised_height = np.where(
            np.isclose(normalised_height, -1.0), -1.0, normalised_height
        )

        theta = np.arcsin(normalised_height)

        normalised_radius = (R - self.Rmaj * self.a_minor) / self.r_minor

        normalised_radius = np.where(
            np.isclose(normalised_radius, 1.0, atol=1e-4), 1.0, normalised_radius
        )
        normalised_radius = np.where(
            np.isclose(normalised_radius, -1.0, atol=1e-4), -1.0, normalised_radius
        )

        thetaR = np.arccos(normalised_radius)

        theta = np.where(R < R_upper, np.pi - theta, theta)
        theta = np.where((R >= R_upper) & (Z < 0), 2 * np.pi + theta, theta)
        thetaR = np.where(Z < 0, 2 * np.pi - thetaR, thetaR)

        # Ensure first point is close to 0 rather than 2pi
        if theta[0] > np.pi:
            theta[0] += -2 * np.pi
            thetaR[0] += -2 * np.pi

        self.theta_eq = theta

        theta_diff = thetaR - theta

        ntheta = np.outer(self.n, theta)

        cn = simpson(theta_diff * np.cos(ntheta), theta, axis=1) / np.pi
        sn = simpson(theta_diff * np.sin(ntheta), theta, axis=1) / np.pi

        self.kappa = kappa
        self.sn = sn
        self.cn = cn

        self.theta = theta
        self.thetaR = self.get_thetaR(self.theta)
        self.dthetaR_dtheta = self.get_dthetaR_dtheta(self.theta)

        self.R, self.Z = self.get_flux_surface(self.theta)

        s_kappa_init = 0.0
        params = [shift, s_kappa_init, 0.0, *[0.0] * self.n_moments * 2]

        fits = least_squares(self.minimise_b_poloidal, params)

        # Check that least squares didn't fail
        if not fits.success:
            raise Exception(
                f"Least squares fitting in MXH::from_global_eq failed with message : {fits.message}"
            )

        if verbose:
            print(f"MXH :: Fit to Bpoloidal obtained with residual {fits.cost}")

        if fits.cost > 0.1:
            import warnings

            warnings.warn(
                f"Warning Fit to Bpoloidal in MXH::from_global_eq is poor with residual of {fits.cost}"
            )

        self.shift = fits.x[0]
        self.s_kappa = fits.x[1]
        self.dZ0dr = fits.x[2]
        self.dcndr = fits.x[3 : self.n_moments + 3]
        self.dsndr = fits.x[self.n_moments + 3 :]

        # Force dsndr[0] which has no impact on flux surface
        self.dsndr[0] = 0.0

        self.dthetaR_dr = self.get_dthetaR_dr(self.theta, self.dcndr, self.dsndr)

    @property
    def n(self):
        return np.linspace(0, self.n_moments - 1, self.n_moments)

    @property
    def n_moments(self):
        return 4

    @property
    def delta(self):
        return np.sin(self.sn[1])

    @delta.setter
    def delta(self, value):
        self.sn[1] = np.arcsin(value)

    @property
    def s_delta(self):
        return self.dsndr[1] * np.sqrt(1 - self.delta**2) * self.rho

    @s_delta.setter
    def s_delta(self, value):
        self.dsndr[1] = value / np.sqrt(1 - self.delta**2) / self.rho

    @property
    def zeta(self):
        return -self["sn"][2]

    @zeta.setter
    def zeta(self, value):
        self["sn"][2] = -value

    @property
    def s_zeta(self):
        return -self.dsndr[2] * self.rho

    @s_zeta.setter
    def s_zeta(self, value):
        self.dsndr[2] = -value / self.rho

    def get_thetaR(self, theta):
        """

        Parameters
        ----------
        theta : Array

        Returns
        -------
        thetaR : Array
            Poloidal angle used in definition of R
        """

        ntheta = np.outer(theta, self.n)

        thetaR = theta + np.sum(
            (self.cn * np.cos(ntheta) + self.sn * np.sin(ntheta)),
            axis=1,
        )

        return thetaR

    def get_dthetaR_dtheta(self, theta):
        """

        Parameters
        ----------
        theta

        Returns
        -------
        dthetaR/dtheta : Array
            theta derivative of poloidal angle used in R
        """

        ntheta = np.outer(theta, self.n)

        dthetaR_dtheta = 1.0 + np.sum(
            (-self.cn * self.n * np.sin(ntheta) + self.sn * self.n * np.cos(ntheta)),
            axis=1,
        )

        return dthetaR_dtheta

    def get_d2thetaR_dtheta2(self, theta):
        """

        Parameters
        ----------
        theta

        Returns
        -------
        d^2thetaR/dtheta^2 : Array
            second theta derivative of poloidal angle used in R
        """

        ntheta = np.outer(theta, self.n)

        d2thetaR_dtheta2 = -np.sum(
            ((self.n**2) * (self.cn * np.cos(ntheta) + self.sn * np.sin(ntheta))),
            axis=1,
        )

        return d2thetaR_dtheta2

    def get_dthetaR_dr(self, theta, dcndr, dsndr):
        """

        Parameters
        ----------
        theta : Array
            theta angles
        dcndr : Array
            Asymmetric coefficients in thetaR
        dsndr : Array
            Symmetric coefficients in thetaR

        Returns
        -------

        """
        ntheta = np.outer(theta, self.n)

        dthetaR_dr = np.sum(
            (dcndr * np.cos(ntheta) + dsndr * np.sin(ntheta)),
            axis=1,
        )

        return dthetaR_dr

    def get_d2thetaR_drdtheta(self, theta, dcndr, dsndr):
        """

        Parameters
        ----------
        theta : Array
            theta angles
        dcndr : Array
            Asymmetric coefficients in thetaR
        dsndr : Array
            Symmetric coefficients in thetaR

        Returns
        -------

        """
        ntheta = np.outer(theta, self.n)

        d2thetaR_drdtheta = np.sum(
            (-self.n * dcndr * np.sin(ntheta) + self.n * dsndr * np.cos(ntheta)),
            axis=1,
        )

        return d2thetaR_drdtheta

    def get_RZ_derivatives(
        self,
        theta: ArrayLike,
        params=None,
        normalised=False,
    ) -> np.ndarray:
        """
        Calculates the derivatives of :math:`R(r, \theta)` and :math:`Z(r, \theta)` w.r.t :math:`r` and :math:`\theta`, used in B_poloidal calc

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate grad_r on
        params : Array [Optional]
            If given then will use params = [shift, s_kappa, dZ0dr, cn[nmoments], sn[nmoments] ] when calculating
            derivatives, otherwise will use object attributes
        normalised : Boolean
            Control whether or not to return normalised values

        Returns
        -------
        dRdtheta : Array
            Derivative of :math:`R` w.r.t :math:`\theta`
        dRdr : Array
            Derivative of :math:`R` w.r.t :math:`r`
        dZdtheta : Array
            Derivative of :math:`Z` w.r.t :math:`\theta`
        dZdr : Array
            Derivative of :math:`Z` w.r.t :math:`r`
        """

        if params is None:
            shift = self.shift
            s_kappa = self.s_kappa
            dZ0dr = self.dZ0dr
            dcndr = self.dcndr
            dsndr = self.dsndr
        else:
            shift = params[0]
            s_kappa = params[1]
            dZ0dr = params[2]
            dcndr = params[3 : self.n_moments + 3]
            dsndr = params[self.n_moments + 3 :]

        thetaR = self.get_thetaR(theta)
        dthetaR_dr = self.get_dthetaR_dr(theta, dcndr, dsndr)
        dthetaR_dtheta = self.get_dthetaR_dtheta(theta)

        dZdtheta = self.get_dZdtheta(theta, normalised)

        dZdr = self.get_dZdr(theta, dZ0dr, s_kappa)

        dRdtheta = self.get_dRdtheta(thetaR, dthetaR_dtheta, normalised)

        dRdr = self.get_dRdr(shift, thetaR, dthetaR_dr)

        return dRdtheta, dRdr, dZdtheta, dZdr

    def get_RZ_second_derivatives(
        self,
        theta: ArrayLike,
        normalised=False,
    ) -> np.ndarray:
        """
        Calculates the second derivatives of :math:`R(r, \theta)` and :math:`Z(r, \theta)` w.r.t :math:`r` and :math:`\theta`, used in geometry terms

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate grad_r on
        normalised : Boolean
            Control whether or not to return normalised values

        Returns
        -------
        d2Rdtheta2 : Array
                        Second derivative of :math:`R` w.r.t :math:`\theta`
        d2Rdrdtheta : Array
                        Second derivative of :math:`R` w.r.t :math:`r` and :math:`\theta`
        d2Zdtheta2 : Array
                        Second derivative of :math:`Z` w.r.t :math:`\theta`
        d2Zdrdtheta : Array
                        Second derivative of :math:`Z` w.r.t :math:`r` and :math:`\theta`
        """

        thetaR = self.get_thetaR(theta)
        dthetaR_dr = self.get_dthetaR_dr(theta, self.dcndr, self.dsndr)
        dthetaR_dtheta = self.get_dthetaR_dtheta(theta)
        d2thetaR_drdtheta = self.get_d2thetaR_drdtheta(theta, self.dcndr, self.dsndr)
        d2thetaR_dtheta2 = self.get_d2thetaR_dtheta2(theta)

        d2Zdtheta2 = self.get_d2Zdtheta2(theta, normalised)
        d2Zdrdtheta = self.get_d2Zdrdtheta(theta, self.s_kappa)
        d2Rdtheta2 = self.get_d2Rdtheta2(
            thetaR, dthetaR_dtheta, d2thetaR_dtheta2, normalised
        )
        d2Rdrdtheta = self.get_d2Rdrdtheta(
            thetaR, dthetaR_dr, dthetaR_dtheta, d2thetaR_drdtheta
        )

        return d2Rdtheta2, d2Rdrdtheta, d2Zdtheta2, d2Zdrdtheta

    def get_dZdtheta(self, theta, normalised=False):
        r"""
        Calculates the derivatives of :math:`Z(r, theta)` w.r.t :math:`\theta`

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate dZdtheta on

        Returns
        -------
        dZdtheta : Array
            Derivative of :math:`Z` w.r.t :math:`\theta`
        """

        if normalised:
            rmin = self.rho
        else:
            rmin = self.r_minor

        return self.kappa * rmin * np.cos(theta)

    def get_d2Zdtheta2(self, theta, normalised=False):
        """
        Calculates the second derivative of :math:`Z(r, theta)` w.r.t :math:`\theta`

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate dZdtheta on

        Returns
        -------
        d2Zdtheta2 : Array
            Second derivative of :math:`Z` w.r.t :math:`\theta`
        """

        if normalised:
            rmin = self.rho
        else:
            rmin = self.r_minor

        return -self.kappa * rmin * np.sin(theta)

    def get_dZdr(self, theta, dZ0dr, s_kappa):
        r"""
        Calculates the derivatives of :math:`Z(r, \theta)` w.r.t :math:`r`

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate dZdr on
        dZ0dr : Float
            Derivative in midplane elevation
        s_kappa : Float
            Shear in Elongation :math:`r/\kappa \partial \kappa/\partial r`

        Returns
        -------
        dZdr : Array
            Derivative of :math:`Z` w.r.t :math:`r`
        """
        return dZ0dr + self.kappa * np.sin(theta) * (1 + s_kappa)

    def get_d2Zdrdtheta(self, theta, s_kappa):
        r"""
        Calculates the second derivative of :math:`Z(r, \theta)` w.r.t :math:`r` and :math:`\theta`

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate dZdr on
        s_kappa : Float
            Shear in Elongation :math:`r/\kappa \partial \kappa/\partial r`

        Returns
        -------
        d2Zdrdtheta : Array
            Second derivative of :math:`Z` w.r.t :math:`r` and :math:`\theta`
        """
        return self.kappa * np.cos(theta) * (1 + s_kappa)

    def get_dRdtheta(self, thetaR, dthetaR_dtheta, normalised=False):
        """
        Calculates the derivatives of :math:`R(r, \theta)` w.r.t :math:`\theta`

        Parameters
        ----------
        thetaR: ArrayLike
            Array of thetaR points to evaluate dRdtheta on
        dthetaR_dtheta : ArrayLike
            Theta derivative of thetaR
        -------
        dRdtheta : Array
            Derivative of :math:`R` w.r.t :math:`\theta`
        """

        if normalised:
            rmin = self.rho
        else:
            rmin = self.r_minor

        return -rmin * np.sin(thetaR) * dthetaR_dtheta

    def get_d2Rdtheta2(
        self, thetaR, dthetaR_dtheta, d2thetaR_dtheta2, normalised=False
    ):
        """
        Calculates the second derivative of :math:`R(r, \theta)` w.r.t :math:`\theta`

        Parameters
        ----------
        thetaR: ArrayLike
            Array of thetaR points to evaluate dRdtheta on
        dthetaR_dtheta : ArrayLike
            Theta derivative of thetaR
        d2thetaR_dtheta2 : ArrayLike
            Second theta derivative of thetaR
        -------
        d2Rdtheta2 : Array
            Second derivative of :math:`R` w.r.t :math:`\theta`
        """

        if normalised:
            rmin = self.rho
        else:
            rmin = self.r_minor

        return -rmin * np.sin(thetaR) * d2thetaR_dtheta2 - rmin * (
            dthetaR_dtheta**2
        ) * np.cos(thetaR)

    def get_dRdr(self, shift, thetaR, dthetaR_dr):
        r"""
        Calculates the derivatives of :math:`R(r, \theta)` w.r.t :math:`r`

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate dRdr on
        shift : Float
            Shafranov shift
        thetaR: ArrayLike
            Array of thetaR points to evaluate dRdtheta on
        dthetaR_dr : ArrayLike
            Radial derivative of thetaR

        Returns
        -------
        dRdr : Array
            Derivative of :math:`R` w.r.t :math:`r`
        """
        return shift + np.cos(thetaR) - self.rho * np.sin(thetaR) * dthetaR_dr

    def get_d2Rdrdtheta(self, thetaR, dthetaR_dr, dthetaR_dtheta, d2thetaR_drdtheta):
        """
        Calculate the second derivative of :math:`R(r, \theta)` w.r.t :math:`r` and :math:`\theta`

        Parameters
        ----------
        theta: ArrayLike
            Array of theta points to evaluate dRdr on
        thetaR: ArrayLike
            Array of thetaR points to evaluate dRdtheta on
        dthetaR_dr : ArrayLike
            Radial derivative of thetaR
        dthetaR_dtheta : ArrayLike
            Theta derivative of thetaR
        d2thetaR_drdtheta : ArrayLike
            Second derivative of thetaR w.r.t :math:`r` and :math:`\theta`

        Returns
        -------
        d2Rdrdtheta : Array
            Second derivative of R w.r.t :math:`r` and :math:`\theta`
        """
        return -dthetaR_dtheta * np.sin(thetaR) - self.rho * (
            np.sin(thetaR) * d2thetaR_drdtheta
            + dthetaR_dr * dthetaR_dtheta * np.cos(thetaR)
        )

    def get_flux_surface(
        self,
        theta: ArrayLike,
        normalised=True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Generates (R,Z) of a flux surface given a set of MXH fits

        Parameters
        ----------
        theta : Array
            Values of theta to evaluate flux surface
        normalised : Boolean
            Control whether or not to return normalised flux surface

        Returns
        -------
        R : Array
            R values for this flux surface (if not normalised then in [m])
        Z : Array
            Z Values for this flux surface (if not normalised then in [m])
        """

        thetaR = self.get_thetaR(theta)

        R = self.Rmaj + self.rho * np.cos(thetaR)
        Z = self.Z0 + self.kappa * self.rho * np.sin(theta)

        if not normalised:
            R *= self.a_minor
            Z *= self.a_minor

        return R, Z

    def default(self):
        """
        Default parameters for geometry
        Same as GA-STD case
        """
        super(LocalGeometryMXH, self).__init__(default_mxh_inputs())
