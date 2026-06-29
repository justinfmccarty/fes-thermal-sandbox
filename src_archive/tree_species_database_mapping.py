from pathlib import Path
import pandas as pd

rows = [
("White Spruce","Picea_glauca","needleleaf"),
("American Elm","Ulmus_americana","broadleaf"),
("Green Ash","Fraxinus_pennsylvanica","broadleaf"),
("Silver Maple","Acer_saccharinum","broadleaf"),
("Siberian Elm","Ulmus_pumila","broadleaf"),
("Russian Olive","Elaeagnus_angustifolia","broadleaf"),
("American Linden","Tilia_americana","broadleaf"),
("Amur Maple","Acer_ginnala","broadleaf"),
("Scots Pine","Pinus_sylvestris","needleleaf"),
("Colorado Blue Spruce","Picea_pungens","needleleaf"),
("Japanese Tree Lilac","Syringa_reticulata","broadleaf"),
("Tamarack","Larix_laricina","needleleaf"),
("Ponderosa Pine","Pinus_ponderosa","needleleaf"),
("Manitoba Maple","Acer_negundo","broadleaf"),
("Bur Oak","Quercus_macrocarpa","broadleaf"),
("Crabapple Rosybloom","Malus_hybrida","broadleaf"),
("Northern Pin Oak","Quercus_ellipsoidalis","broadleaf"),
("Hackberry","Celtis_occidentalis","broadleaf"),
("Elm-Japanese","Ulmus_davidiana_var_japonica","broadleaf"),
("Amur Chokecherry","Prunus_maackii","broadleaf"),
("Dropmore Linden","Tilia_×_flavescens","broadleaf"),
("Juniper","Juniperus_spp","needleleaf"),
("Black Ash","Fraxinus_nigra","broadleaf"),
("Ash-Mancana","Fraxinus_mandshurica","broadleaf"),
("Tower Poplar","Populus_×_canescens","broadleaf"),
("Schubert Chokecherry","Prunus_virginiana_Schubert","broadleaf"),
("Cedar","Thuja_spp","needleleaf"),
("Hawthorn","Crataegus_spp","broadleaf"),
("Siberian Crabapple","Malus_baccata","broadleaf"),
("Showy Mountain Ash","Sorbus_decora","broadleaf"),
("Black Spruce","Picea_mariana","needleleaf"),
("Ohio buckeye","Aesculus_glabra","broadleaf"),
("Alder","Alnus_spp","broadleaf"),
]


naming_dict = {
    "White Spruce":"Picea_glauca",
    "American Elm":"Ulmus_americana",
    "Green Ash":"Fraxinus_pennsylvanica",
    "Silver Maple":"Acer_saccharinum",
    "Siberian Elm":"Ulmus_pumila",
    "Russian Olive":"Elaeagnus_angustifolia",
    "American Linden":"Tilia_americana",
    "Amur Maple":"Acer_ginnala",
    "Scots Pine":"Pinus_sylvestris",
    "Colorado Blue Spruce":"Picea_pungens",
    "Japanese Tree Lilac":"Syringa_reticulata",
    "Tamarack":"Larix_laricina",
    "Ponderosa Pine":"Pinus_ponderosa",
    "Manitoba Maple":"Acer_negundo",
    "Bur Oak":"Quercus_macrocarpa",
    "Crabapple Rosybloom":"Malus_hybrida",
    "Northern Pin Oak":"Quercus_ellipsoidalis",
    "Hackberry":"Celtis_occidentalis",
    "Elm-Japanese":"Ulmus_davidiana_var_japonica",
    "Amur Chokecherry":"Prunus_maackii",
    "Dropmore Linden":"Tilia_×_flavescens",
    "Juniper":"Juniperus_spp",
    "Black Ash":"Fraxinus_nigra",
    "Ash-Mancana":"Fraxinus_mandshurica",
    "Tower Poplar":"Populus_×_canescens",
    "Schubert Chokecherry":"Prunus_virginiana_Schubert",
    "Cedar":"Thuja_spp",
    "Hawthorn":"Crataegus_spp",
    "Siberian Crabapple":"Malus_baccata",
    "Showy Mountain Ash":"Sorbus_decora",
    "Black Spruce":"Picea_mariana",
    "Ohio buckeye":"Aesculus_glabra",
    "Alder":"Alnus_spp",
}

k_broadleaf = 0.59
k_needleleaf = 0.45

alpha_broadleaf = 0.275
alpha_needleleaf = 0.210

eps_leaf = 0.98

gsmax_broadleaf = 0.25
gsmax_needleleaf = 0.20

g1_broadleaf = 4.45
g1_needleleaf = 2.35

Topt = 36.0
Tcrit = 47.0

citations = (
"Zhang et al. 2014 canopy extinction k means citeturn0search0; "
"Bonan et al. 2002 CLM2 leaf reflectance VIS/NIR (Table 4) used here as SW albedo proxy citeturn8view0; "
"López et al. 2012 leaf emissivity ~0.98 citeturn0search2; "
"De Kauwe et al. 2015 g1 PFT values (Table 1) citeturn3search3; "
"Murray et al. 2019 gsmax ~250 mmol m−2 s−1 for C3 woody angiosperms citeturn9search13; "
"Robakowski et al. 2002 PSII critical temperature ~47°C citeturn0search7"
)

out = []
for common, latin, pft in rows:
    if pft == "needleleaf":
        out.append({
            "common_name": common,
            "species": latin,
            "light_extinction_coefficient": k_needleleaf,
            "leaf_shortwave_albedo": alpha_needleleaf,
            "leaf_emissivity": eps_leaf,
            "max_stomatal_conductance_mol_m2_s": gsmax_needleleaf,
            "vpd_sensitivity_g1_kpa_sqrt": g1_needleleaf,
            "optimal_leaf_temperature_c": Topt,
            "critical_leaf_temperature_c": Tcrit,
            "citations": citations
        })
    else:
        out.append({
            "common_name": common,
            "species": latin,
            "light_extinction_coefficient": k_broadleaf,
            "leaf_shortwave_albedo": alpha_broadleaf,
            "leaf_emissivity": eps_leaf,
            "max_stomatal_conductance_mol_m2_s": gsmax_broadleaf,
            "vpd_sensitivity_g1_kpa_sqrt": g1_broadleaf,
            "optimal_leaf_temperature_c": Topt,
            "critical_leaf_temperature_c": Tcrit,
            "citations": citations
        })

df = pd.DataFrame(out)
path = Path("tree_species_database.csv")
df.to_csv(path, index=False)


