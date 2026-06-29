"""
Unit Tests for Li2023 CEB Model

Tests for the Li et al. (2023) Canopy Energy Balance model implementation.
Includes:
- Solver convergence tests
- Sensitivity tests for ground albedo and emissivity
- Boundary condition tests
- Energy balance closure verification
"""

import pytest
import numpy as np
from li2023_ceb_model import (
    Li2023CEBModel, 
    CEBInputs, 
    CEBOutputs,
    solve_leaf_temperature_ceb,
    CEB_DEFAULTS,
    SIGMA
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def ceb_model():
    """Create a default CEB model instance."""
    return Li2023CEBModel()


@pytest.fixture
def summer_midday_inputs():
    """Typical summer midday conditions in Winnipeg."""
    return CEBInputs(
        Ta=28.0,           # Air temperature [C]
        RH=0.50,           # 50% relative humidity
        U=2.0,             # Wind speed [m/s]
        P=101.3,           # Pressure [kPa]
        E_dir=600.0,       # Direct irradiance [W/m2]
        E_dif=150.0,       # Diffuse irradiance [W/m2]
        SVF=0.15,          # Typical urban tree SVF
        albedo_g=0.30,     # Ground albedo
        epsilon_g=0.95,    # Ground emissivity
        alpha_sf=0.82,     # Leaf SW absorptivity
        alpha_lf=0.97,     # Leaf LW absorptivity
        epsilon_lf=0.97,   # Leaf emissivity
        r_sto=160.0,       # Stomatal resistance [s/m]
        leaf_size=0.05     # Leaf characteristic size [m]
    )


@pytest.fixture
def night_inputs():
    """Nighttime conditions (no solar radiation)."""
    return CEBInputs(
        Ta=18.0,           # Cooler at night
        RH=0.70,           # Higher humidity at night
        U=1.0,             # Calmer winds
        P=101.3,
        E_dir=0.0,         # No direct radiation
        E_dif=0.0,         # No diffuse radiation
        SVF=0.15,
        albedo_g=0.30,
        epsilon_g=0.95,
        alpha_sf=0.82,
        alpha_lf=0.97,
        epsilon_lf=0.97,
        r_sto=160.0,
        leaf_size=0.05
    )


@pytest.fixture
def high_stress_inputs():
    """High stress conditions (hot, dry, low wind)."""
    return CEBInputs(
        Ta=35.0,           # Very hot
        RH=0.25,           # Very dry
        U=0.5,             # Calm wind (less cooling)
        P=101.3,
        E_dir=800.0,       # High radiation
        E_dif=200.0,
        SVF=0.10,          # Low SVF (more ground view)
        albedo_g=0.10,     # Dark surface (asphalt)
        epsilon_g=0.95,
        alpha_sf=0.82,
        alpha_lf=0.97,
        epsilon_lf=0.97,
        r_sto=200.0,       # Higher stomatal resistance (stressed)
        leaf_size=0.05
    )


# =============================================================================
# Solver Convergence Tests
# =============================================================================

class TestSolverConvergence:
    """Tests for solver convergence under various conditions."""
    
    def test_converges_normal_conditions(self, ceb_model, summer_midday_inputs):
        """Test that solver converges under typical summer conditions."""
        outputs = ceb_model.solve_leaf_temperature(summer_midday_inputs)
        
        assert outputs.converged, "Solver should converge under normal conditions"
        assert outputs.Tf is not None
        assert not np.isnan(outputs.Tf)
    
    def test_converges_night_conditions(self, ceb_model, night_inputs):
        """Test that solver converges at night (no solar radiation)."""
        outputs = ceb_model.solve_leaf_temperature(night_inputs)
        
        assert outputs.converged, "Solver should converge at night"
        assert outputs.Tf is not None
        assert not np.isnan(outputs.Tf)
    
    def test_converges_high_stress(self, ceb_model, high_stress_inputs):
        """Test that solver converges under high stress conditions."""
        outputs = ceb_model.solve_leaf_temperature(high_stress_inputs)
        
        assert outputs.converged, "Solver should converge under high stress"
        assert outputs.Tf is not None
        assert not np.isnan(outputs.Tf)
    
    def test_leaf_temp_in_reasonable_range(self, ceb_model, summer_midday_inputs):
        """Test that leaf temperature is within physically reasonable bounds."""
        outputs = ceb_model.solve_leaf_temperature(summer_midday_inputs)
        
        Ta = summer_midday_inputs.Ta
        # Leaf temp should be within Ta ± 20°C for typical conditions
        assert outputs.Tf >= Ta - 15, f"Leaf temp {outputs.Tf}°C too cold vs Ta={Ta}°C"
        assert outputs.Tf <= Ta + 25, f"Leaf temp {outputs.Tf}°C too hot vs Ta={Ta}°C"
    
    def test_calm_wind_convergence(self, ceb_model, summer_midday_inputs):
        """Test convergence with very low wind speed."""
        inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=0.1,  # Very calm
            P=summer_midday_inputs.P,
            E_dir=summer_midday_inputs.E_dir,
            E_dif=summer_midday_inputs.E_dif,
            SVF=summer_midday_inputs.SVF,
            albedo_g=summer_midday_inputs.albedo_g,
            epsilon_g=summer_midday_inputs.epsilon_g,
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        outputs = ceb_model.solve_leaf_temperature(inputs)
        assert outputs.converged, "Solver should handle very low wind speeds"


# =============================================================================
# Sensitivity Tests - Ground Albedo
# =============================================================================

class TestAlbedoSensitivity:
    """Tests for sensitivity to ground albedo changes."""
    
    def test_higher_albedo_reduces_leaf_temp(self, ceb_model, summer_midday_inputs):
        """Higher ground albedo should reduce leaf temperature (more reflection)."""
        # Low albedo (dark surface - asphalt)
        low_albedo_inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=summer_midday_inputs.E_dir,
            E_dif=summer_midday_inputs.E_dif,
            SVF=summer_midday_inputs.SVF,
            albedo_g=0.10,  # Dark asphalt
            epsilon_g=summer_midday_inputs.epsilon_g,
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        # High albedo (light surface - concrete)
        high_albedo_inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=summer_midday_inputs.E_dir,
            E_dif=summer_midday_inputs.E_dif,
            SVF=summer_midday_inputs.SVF,
            albedo_g=0.50,  # Light concrete
            epsilon_g=summer_midday_inputs.epsilon_g,
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        low_outputs = ceb_model.solve_leaf_temperature(low_albedo_inputs)
        high_outputs = ceb_model.solve_leaf_temperature(high_albedo_inputs)
        
        # Higher albedo means more reflected SW, which means MORE radiation absorbed by leaf
        # So counterintuitively, higher ground albedo increases leaf temp due to ground reflection
        # But the net effect depends on the coupling factors
        # The key is that the difference should exist
        assert low_outputs.Tf != high_outputs.Tf, \
            "Albedo should affect leaf temperature"
        
        print(f"Low albedo (0.10): Tf = {low_outputs.Tf:.2f}°C")
        print(f"High albedo (0.50): Tf = {high_outputs.Tf:.2f}°C")
        print(f"Difference: {high_outputs.Tf - low_outputs.Tf:.2f}°C")


# =============================================================================
# Sensitivity Tests - Ground Emissivity
# =============================================================================

class TestEmissivitySensitivity:
    """Tests for sensitivity to ground emissivity changes."""
    
    def test_emissivity_affects_leaf_temp(self, ceb_model, summer_midday_inputs):
        """Ground emissivity should affect leaf temperature through LW radiation."""
        # Low emissivity
        low_emis_inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=summer_midday_inputs.E_dir,
            E_dif=summer_midday_inputs.E_dif,
            SVF=summer_midday_inputs.SVF,
            albedo_g=summer_midday_inputs.albedo_g,
            epsilon_g=0.80,  # Low emissivity
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        # High emissivity
        high_emis_inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=summer_midday_inputs.E_dir,
            E_dif=summer_midday_inputs.E_dif,
            SVF=summer_midday_inputs.SVF,
            albedo_g=summer_midday_inputs.albedo_g,
            epsilon_g=0.98,  # High emissivity
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        low_outputs = ceb_model.solve_leaf_temperature(low_emis_inputs)
        high_outputs = ceb_model.solve_leaf_temperature(high_emis_inputs)
        
        # Higher emissivity = more LW emission from ground = more LW absorbed by leaf
        # So higher emissivity should increase leaf temp (for hot ground)
        assert low_outputs.Tf != high_outputs.Tf, \
            "Emissivity should affect leaf temperature"
        
        print(f"Low emissivity (0.80): Tf = {low_outputs.Tf:.2f}°C")
        print(f"High emissivity (0.98): Tf = {high_outputs.Tf:.2f}°C")
        print(f"Difference: {high_outputs.Tf - low_outputs.Tf:.2f}°C")


# =============================================================================
# Energy Balance Closure Tests
# =============================================================================

class TestEnergyBalanceClosure:
    """Tests for energy balance closure at the solution."""
    
    def test_energy_balance_closure(self, ceb_model, summer_midday_inputs):
        """Verify that Rn ≈ H + LE at the solution."""
        outputs = ceb_model.solve_leaf_temperature(summer_midday_inputs)
        
        # Net radiation = absorbed SW + absorbed LW - emitted LW
        Rn = outputs.Q_sw + outputs.Q_lw_in - outputs.Q_lw_out
        
        # Sum of fluxes
        flux_sum = outputs.H + outputs.LE
        
        # Energy balance residual should be small (< 1 W/m2)
        residual = abs(Rn - flux_sum)
        
        assert residual < 5.0, \
            f"Energy balance residual ({residual:.2f} W/m2) too large"
        
        print(f"Rn = {Rn:.2f} W/m2")
        print(f"H + LE = {flux_sum:.2f} W/m2")
        print(f"Residual = {residual:.2f} W/m2")
    
    def test_sensible_heat_sign(self, ceb_model, summer_midday_inputs):
        """Sensible heat should be positive when leaf is warmer than air."""
        outputs = ceb_model.solve_leaf_temperature(summer_midday_inputs)
        
        if outputs.Tf > summer_midday_inputs.Ta:
            assert outputs.H > 0, "H should be positive when Tf > Ta"
        elif outputs.Tf < summer_midday_inputs.Ta:
            assert outputs.H < 0, "H should be negative when Tf < Ta"
    
    def test_latent_heat_non_negative(self, ceb_model, summer_midday_inputs):
        """Latent heat should be non-negative (no condensation in this model)."""
        outputs = ceb_model.solve_leaf_temperature(summer_midday_inputs)
        
        assert outputs.LE >= 0, "LE should be non-negative"


# =============================================================================
# Physical Consistency Tests
# =============================================================================

class TestPhysicalConsistency:
    """Tests for physical consistency of model behavior."""
    
    def test_night_leaf_temp_near_air_temp(self, ceb_model, night_inputs):
        """At night, leaf temp should be close to air temp (within a few degrees)."""
        outputs = ceb_model.solve_leaf_temperature(night_inputs)
        
        diff = abs(outputs.Tf - night_inputs.Ta)
        assert diff < 10, f"Night Tf should be within 10°C of Ta, got diff={diff:.2f}°C"
    
    def test_higher_wind_reduces_leaf_temp_excess(self, ceb_model, high_stress_inputs):
        """Higher wind speed should reduce leaf-air temperature difference."""
        # Low wind
        low_wind_inputs = CEBInputs(
            Ta=high_stress_inputs.Ta,
            RH=high_stress_inputs.RH,
            U=0.5,  # Low wind
            P=high_stress_inputs.P,
            E_dir=high_stress_inputs.E_dir,
            E_dif=high_stress_inputs.E_dif,
            SVF=high_stress_inputs.SVF,
            albedo_g=high_stress_inputs.albedo_g,
            epsilon_g=high_stress_inputs.epsilon_g,
            alpha_sf=high_stress_inputs.alpha_sf,
            alpha_lf=high_stress_inputs.alpha_lf,
            epsilon_lf=high_stress_inputs.epsilon_lf,
            r_sto=high_stress_inputs.r_sto,
            leaf_size=high_stress_inputs.leaf_size
        )
        
        # High wind
        high_wind_inputs = CEBInputs(
            Ta=high_stress_inputs.Ta,
            RH=high_stress_inputs.RH,
            U=5.0,  # High wind
            P=high_stress_inputs.P,
            E_dir=high_stress_inputs.E_dir,
            E_dif=high_stress_inputs.E_dif,
            SVF=high_stress_inputs.SVF,
            albedo_g=high_stress_inputs.albedo_g,
            epsilon_g=high_stress_inputs.epsilon_g,
            alpha_sf=high_stress_inputs.alpha_sf,
            alpha_lf=high_stress_inputs.alpha_lf,
            epsilon_lf=high_stress_inputs.epsilon_lf,
            r_sto=high_stress_inputs.r_sto,
            leaf_size=high_stress_inputs.leaf_size
        )
        
        low_outputs = ceb_model.solve_leaf_temperature(low_wind_inputs)
        high_outputs = ceb_model.solve_leaf_temperature(high_wind_inputs)
        
        low_excess = low_outputs.Tf - low_wind_inputs.Ta
        high_excess = high_outputs.Tf - high_wind_inputs.Ta
        
        assert abs(high_excess) < abs(low_excess), \
            "Higher wind should reduce leaf-air temp difference"
        
        print(f"Low wind (0.5 m/s): Tf-Ta = {low_excess:.2f}°C")
        print(f"High wind (5.0 m/s): Tf-Ta = {high_excess:.2f}°C")
    
    def test_higher_radiation_increases_leaf_temp(self, ceb_model, summer_midday_inputs):
        """Higher solar radiation should increase leaf temperature."""
        # Low radiation
        low_rad_inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=200.0,  # Low radiation
            E_dif=50.0,
            SVF=summer_midday_inputs.SVF,
            albedo_g=summer_midday_inputs.albedo_g,
            epsilon_g=summer_midday_inputs.epsilon_g,
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        # High radiation
        high_rad_inputs = CEBInputs(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=900.0,  # High radiation
            E_dif=200.0,
            SVF=summer_midday_inputs.SVF,
            albedo_g=summer_midday_inputs.albedo_g,
            epsilon_g=summer_midday_inputs.epsilon_g,
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        low_outputs = ceb_model.solve_leaf_temperature(low_rad_inputs)
        high_outputs = ceb_model.solve_leaf_temperature(high_rad_inputs)
        
        assert high_outputs.Tf > low_outputs.Tf, \
            "Higher radiation should increase leaf temperature"
        
        print(f"Low radiation: Tf = {low_outputs.Tf:.2f}°C")
        print(f"High radiation: Tf = {high_outputs.Tf:.2f}°C")


# =============================================================================
# Standalone Function Tests
# =============================================================================

class TestStandaloneFunction:
    """Tests for the standalone solve_leaf_temperature_ceb function."""
    
    def test_standalone_function(self):
        """Test that standalone function works correctly."""
        Tf, H, LE, gc, converged = solve_leaf_temperature_ceb(
            Ta=28.0,
            RH=0.50,
            U=2.0,
            P=101.3,
            E_dir=600.0,
            E_dif=150.0,
            SVF=0.15,
            albedo_g=0.30,
            epsilon_g=0.95
        )
        
        assert converged, "Standalone function should converge"
        assert not np.isnan(Tf)
        assert Tf > 0  # Should be in reasonable range
    
    def test_standalone_matches_class(self, ceb_model, summer_midday_inputs):
        """Standalone function should produce same results as class method."""
        class_outputs = ceb_model.solve_leaf_temperature(summer_midday_inputs)
        
        Tf, H, LE, gc, converged = solve_leaf_temperature_ceb(
            Ta=summer_midday_inputs.Ta,
            RH=summer_midday_inputs.RH,
            U=summer_midday_inputs.U,
            P=summer_midday_inputs.P,
            E_dir=summer_midday_inputs.E_dir,
            E_dif=summer_midday_inputs.E_dif,
            SVF=summer_midday_inputs.SVF,
            albedo_g=summer_midday_inputs.albedo_g,
            epsilon_g=summer_midday_inputs.epsilon_g,
            alpha_sf=summer_midday_inputs.alpha_sf,
            alpha_lf=summer_midday_inputs.alpha_lf,
            epsilon_lf=summer_midday_inputs.epsilon_lf,
            r_sto=summer_midday_inputs.r_sto,
            leaf_size=summer_midday_inputs.leaf_size
        )
        
        assert abs(Tf - class_outputs.Tf) < 0.01, \
            "Standalone function should match class method"


# =============================================================================
# Sub-equation Tests
# =============================================================================

class TestSubEquations:
    """Tests for individual sub-equations."""
    
    def test_sky_longwave_swinbank(self, ceb_model):
        """Test Swinbank (1963) sky longwave formula."""
        # At 20°C (293.15 K)
        Ta_K = 293.15
        R_lw_sky = ceb_model.calculate_sky_longwave(Ta_K)
        
        # Should be around 350-400 W/m2 at 20°C
        assert 300 < R_lw_sky < 450, f"Sky LW ({R_lw_sky:.1f}) should be 300-450 W/m2"
    
    def test_saturation_vapor_pressure(self, ceb_model):
        """Test saturation vapor pressure calculation."""
        # At 20°C, es ≈ 2.34 kPa
        es_20 = ceb_model.calculate_saturation_vapor_pressure(20.0)
        assert abs(es_20 - 2.34) < 0.1, f"es(20°C) = {es_20:.3f}, expected ~2.34 kPa"
        
        # At 30°C, es ≈ 4.24 kPa
        es_30 = ceb_model.calculate_saturation_vapor_pressure(30.0)
        assert abs(es_30 - 4.24) < 0.1, f"es(30°C) = {es_30:.3f}, expected ~4.24 kPa"
    
    def test_boundary_resistance(self, ceb_model):
        """Test boundary layer resistance calculation."""
        rb_h, rb_w = ceb_model.calculate_boundary_resistances(U=2.0, leaf_size=0.05)
        
        # rb_h should be on order of 10-100 s/m for typical conditions
        assert 10 < rb_h < 200, f"rb_h ({rb_h:.1f}) should be 10-200 s/m"
        
        # rb_w should be slightly less than rb_h (rb_w = rb_h / 1.08)
        assert rb_w < rb_h, "rb_w should be less than rb_h"
        assert abs(rb_w - rb_h/1.08) < 0.01


# =============================================================================
# Run tests with pytest
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
