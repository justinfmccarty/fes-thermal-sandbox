# Task: Add ground temperature (Tg) and soil moisture bucket to support Li-et-al. leaf temperature model

This is an **update to the existing Li et al. CEB leaf-temperature implementation**.  
Do not replace that model. Instead, add two coupled subsystems that provide it with:

- **Ground surface temperature (Tg)**
- **Soil-moisture–driven stomatal resistance (r_sto)**

These must be lightweight, fast, and scenario-sensitive to **ground albedo and emissivity**.

---

## Part A — Ground temperature model (Tg)

### Purpose
The Li et al. leaf model requires **ground longwave emission**:
\[
R_{lw,\uparrow} = \varepsilon_g \sigma T_g^4
\]
but Tg is not currently computed. Tg must reflect:
- albedo (solar absorption)
- emissivity (radiative cooling)
- thermal mass (pavement vs soil vs turf)
- diurnal forcing

We need a **low-order, physically consistent** Tg model.

---

### Use a 1-layer surface energy balance

Per ground patch (at each tree’s sensor location or class):

Solve:
\[
C_g \frac{dT_g}{dt} = (1-\alpha_g)K_{\downarrow}
+ L_{\downarrow}
- \varepsilon_g \sigma T_g^4
- H_g
- LE_g
\]

Where:
- \(K_{\downarrow}\) comes from Radiance sensor (same E_dir + E_dif)
- \(\alpha_g\) = ground albedo (scenario variable)
- \(\varepsilon_g\) = ground emissivity (scenario variable)
- \(C_g\) = effective heat capacity (depends on surface type)
- \(H_g = \rho c_p (T_g - T_a) / r_{a,g}\)
- \(LE_g = \lambda E_g\) (can be 0 for impervious, or simple for pervious)

This can be solved explicitly:
\[
T_g(t+1) = T_g(t) + \Delta t \cdot \frac{R_{net}}{C_g}
\]

---

### Required ground parameters (root DB)

Add a **surface type table** with:

- `albedo`
- `emissivity`
- `heat_capacity_J_m2_K`  (≈ density × depth × cp)
- `evaporation_factor`   (0 for pavement, 0.2–1 for soil/turf)
- `aerodynamic_resistance` (or roughness class)

This allows:
- concrete vs asphalt vs turf vs soil
- thermal mass to emerge naturally

---

### Why this is required

Without Tg:
- changing emissivity only affects LW mathematically, not physically
- thermal inertia of pavement vs grass is invisible
- night-time urban heat storage cannot be represented

This Tg model provides that missing physics at minimal cost.

---

## Part B — Soil moisture bucket for stomatal stress

### Purpose
Li et al. assume “sufficient soil moisture” and use a constant stomatal resistance `r_sto`.  
For urban stress and risk, **this is unacceptable**.

We must compute soil moisture and feed it into `r_sto`.

---

### Use a 1-layer root-zone water balance

For each tree:

\[
\theta(t+1) = \theta(t) + \frac{P + I - ET - D}{Z_r}
\]

Where:
- `θ` = volumetric soil moisture
- `P` = precipitation
- `I` = irrigation
- `ET` = transpiration from Li model (`LE / λ`)
- `D` = drainage when θ > θ_fc
- `Z_r` = root-zone depth

Drainage rule:
if θ > θ_fc:
D = k_drain * (θ - θ_fc)
else:
D = 0


---

### Soil-moisture stress function

Compute relative extractable water:
\[
REW = \frac{\theta - \theta_{wilt}}{\theta_{fc} - \theta_{wilt}}
\]

Define stress multiplier:
if REW > 0.4: fSM = 1
if REW < 0.4: fSM = REW / 0.4


---

### Convert to stomatal resistance

Baseline species value:
r_sto_min (from species DB)




Actual value used in Li model:
r_sto = r_sto_min / fSM



So:
- wet soil → strong transpiration → cooler leaves
- dry soil → stomata close → hot leaves → heat stress emerges

---

## Part C — Coupling to Li et al. leaf model

At every timestep per tree:

1. Update Tg using ground EB
2. Update soil moisture using ET from previous step
3. Compute `r_sto` from soil moisture
4. Pass `Tg`, `εg`, and `r_sto` into Li leaf-temperature solver
5. Solve for `Tleaf`
6. Compute ET from `LE`
7. Loop

---

## Part D — Outputs for scenario analysis

You must expose:
- `Tg`
- `θ` (soil moisture)
- `r_sto`
- `Tleaf`
- `LE`

So scenario differences in:
- albedo
- emissivity
- paving vs turf
- irrigation

can be traced to physical causes.

---

## Part E — Ask me if missing

Before implementing:
Ask me:
- Which ground types exist (pavement, turf, soil, etc.)
- Whether irrigation is modeled
- What soil texture to assume
- Whether drainage should be fast (urban soil) or slow (park soil)

Do not stall — propose defaults and make them configurable.

---

## Success criterion

After this update:
- Changing albedo or emissivity changes Tg
- Changing Tg changes longwave to leaves
- Dry soil increases r_sto
- Higher r_sto increases leaf temperature
- Heat waves + drought produce compounding stress

That is the physics we need.





