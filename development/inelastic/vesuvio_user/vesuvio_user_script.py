"""
Main driver script for VESUVIO users

It requires the VesuvioReduction algorithm
"""
import mantid
from mantid.simpleapi import VesuvioReduction

# --------------------------------------------------------------------------------
# Standard flags to modify processing
# --------------------------------------------------------------------------------

# Specify the run(s) to process. Can be either a single number or a list of
# two numbers defining ranges
# Example: "15039" will process the single run
# Example 2: "15039-15045" will process the sum of range 14188-15045
# Example 2: "15039,15045" will process the sum of 14188,15045
runs = "15039-15045"

# Fitting mode. Options are:
#    bank: spectra from each bank are summed and each bank is then fitted separately
#    spectrum: spectra are fitted individually
fit_mode = 'bank'

# Spectra selection. Can be a single number, a list of two numbers defining a range
# or one of the keyword strings "forward" or "backward"
# Example: 135 will only process spectrum 135 (only applies if fit_mode="spectrum")
# Example 2: 135-185 will process all spectra in the range (only applies if fit_mode="spectrum")
# Example 3: "forward" will process all spectra in the forward scattering banks
spectra = 'forward'

# Masses and properties for fit. Each mass is a dictionary of properties about that mass
# All functions require the following keywords:
#   'value': The mass value itself
#   'function': The name of the function approximate the mass profile: GramCharlier/Gaussian
#   'width': The value/values for the width. A single number specifies a fixed width whereas
#            a list of numbers specifies a default and allowed range for the width as [min,default,max]
# If the function is set to GramCharlier (generally only for the first mass) then there are additional
# keywords:
#    'hermite_coeffs': A list of 1/0 to indicate whether a given coefficient is included
#    'k_free': True/False to indicate whether k is either fixed or remains free
#    'sears_flag': If k is fixed then sears_flag=1 fixes k=sqrt(2)/12 whereas sears_flag=0
#                 fixes k=0
mass1 = {'value': 1.0079, 'function': 'GramCharlier', 'width': [2, 5, 7],
          'hermite_coeffs': [1,0,0], 'k_free': 1, 'sears_flag': 1}
mass2 = {'value': 16.0, 'function': 'Gaussian', 'width': 10}
mass3 = {'value': 27.0, 'function': 'Gaussian', 'width': 13}
mass4 = {'value': 133.0, 'function': 'Gaussian', 'width': 30}
masses = [mass1, mass2, mass3, mass4]

#
# #   'masses' defines the actual mass values
# masses = [1.0079, 16, 27, 133]
# #   'functions' defines the type of profile function in a fit for each mass and should match the length of masses
# # 'GramCharlier' should generally be used for the first mass only. There are extra
# #  keys required if it used:
# functions = ["GramCharlier", "Gaussian", "Gaussian", "Gaussian"]
# # 'fixed_widths' defines the values of those widths that are fixed and should match the length of masses
# # A 0 should be used for a width that will not be fixed.
# fixed_widths = [0, 10, 13, 30]
# # 'width_ranges' is only required if there are some unfixed widths above. If there are none set this to an
# # empty list, else there should be 3 values (min,default,max) per unfixed mass.
# width_ranges = [2, 5, 7]

# Intensity constraints. Can be None or a tuple of lists defining the required
# constraints to be imposed between the intensity values for each mass.
# Example 1: ([0, 1, 0, -4]) defines a single constraint that the intensity of mass 2
#            should be 4 times the intensity of mass 4
constraints = ([0, 1, 0, -4])

# --------------------------------------------------------------------------------
# Advanced flags
# --------------------------------------------------------------------------------

# Calibration file specifying the detector positions and parameter values
ip_file = 'IP0004_10.par'

# Differencing mode. You should rarely need to modify this. Options are:
#    single
#    double
diff_mode = 'single'

# --------------------------------------------------------------------------------
# Processing
# --------------------------------------------------------------------------------
# Put the function arguments into something the algorithm can understand
mass_values, profiles = [], []
for mass_prop in masses:
    function_props = []
    for key, value in mass_prop.iteritems():
        if key == 'value':
            mass_values.append(value)
        else:
             function_props.append("{0}={1}".format(key,value))
    profiles.append(",".join(function_props))

profiles = ";".join(profiles)
print profiles
fitted, params = VesuvioReduction(Runs=runs, IPFilename=ip_file,
                 Masses=masses,
                 MassProfiles=profiles,
                 DifferenceMode=diff_mode)