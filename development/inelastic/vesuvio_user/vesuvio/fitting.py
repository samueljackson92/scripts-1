"""Fitting support routines
"""
import re

from profiles import create_profile_from_str

# --------------------------------------------------------------------------------
# Functions
# --------------------------------------------------------------------------------

def parse_fit_options(mass_values, profiles):
    """Parse the function string into a more usable format"""

    # Individual functions are separated by semi-colon separators
    mass_functions = profiles.split(";")
    profiles = []
    for mass_value, prop_str in zip(mass_values, mass_functions):
        profiles.append(create_profile_from_str(prop_str, mass_value))

    print "WARNING: No constraints set"
    fit_opts = FittingOptions(profiles, None)
    return fit_opts

# --------------------------------------------------------------------------------
# FittingOptions
# --------------------------------------------------------------------------------

class FittingOptions(object):
    """Holds all of the parameters for the fitting that are not related to the domain"""

    def __init__(self, profiles, constraints):
        self.smooth_points = None
        self.bad_data_error = None

        self.mass_profiles = profiles
        self.background_function = None
        self.background_order = None
        self.constraints = constraints

        self.global_fit = False
        self.output_prefix = None

    def has_been_set(self, name):
        """Returns true if the given option has been set by the user
        """
        return getattr(self, name) is not None

    # -------------------------------------------------------------------------------------------------------------

    def create_function_str(self, default_vals=None):
        """
            Creates the function string to pass to fit

            @param default_vals: A dictionary of key/values specifying the parameter values
            that have already been calculated. If None then the ComptonScatteringCountRate
            function, along with the constraints matrix, is used rather than the standard CompositeFunction.
            It is assumed that the standard CompositeFunction is used when running the fit for a
            second time to compute the errors with everything free
        """
        all_free = (default_vals is not None)

        if all_free:
            function_str = "composite=CompositeFunction,NumDeriv=1;"
        else:
            function_str = "composite=ComptonScatteringCountRate,NumDeriv=1%s;"
            matrix_str = self.create_matrix_string(self.constraints)
            if matrix_str == "":
                function_str = function_str % ""
            else:
                function_str = function_str % (",IntensityConstraints=" + matrix_str)

        for index, mass_profile in enumerate(self.mass_profiles):
            par_prefix = "f{0}.".format(index)
            function_str += mass_profile.create_fitting_str(default_vals, par_prefix)

        # Add on a background polynomial if requested
        if self.has_been_set("background_order"):
            if not isinstance(self.background_order, types.IntType):
                raise RuntimeError("background_order parameter should be an integer, found '%s'" % type(self.background_order))
            if self.has_been_set("background_function"):
                if not isinstance(self.background_function, types.StringType):
                    raise RuntimeError("background_function parameter should be a string, found '%s'" % type(self.background_function))
                background_func = self.background_function
            else:
                background_func = self._defaults["background_function"]
            background_str = "name=%s,n=%d" % (background_func,self.background_order)
            if all_free:
                func_index = len(self.masses)
                for power in range (0,self.background_order+1):
                    param_name = 'A%d' % (power)
                    comp_par_name = 'f%d.%s' % (func_index,param_name)
                    background_str += ",%s=%f" % (param_name,param_values[comp_par_name])
            function_str += "%s" % background_str.rstrip(",")

        return function_str.rstrip(";")

    def create_matrix_string(self, constraints_tuple):
        """Returns a string for the value of the Matrix of intensity
        constraint values
        """
        if self.constraints is None or len(self.constraints) == 0:
            return ""

        if hasattr(self.constraints[0], "__len__"):
            nrows = len(self.constraints)
            ncols = len(self.constraints[0])
        else:
            nrows = 1
            # without trailing comma a single-element tuple is automatically
            # converted to just be the element
            ncols = len(self.constraints)
            # put back in sequence

        matrix_str = "\"Matrix(%d|%d)%s\""
        values = ""
        for row in self.constraints:
            for val in row:
                values += "%f|" % val
        values = values.rstrip("|")
        matrix_str = matrix_str % (nrows, ncols, values)
        return matrix_str

    def create_constraints_str(self):
        """Returns the string of constraints for this Fit
        """
        constraints = ""
        for index, mass_info in enumerate(self.masses):
            # Constraints
            func_index = index
            par_name = "f%d.Width" % func_index
            widths = mass_info['widths']
            if hasattr(widths, "__len__"):
                constraints += "%f < %s < %f," % (widths[0], par_name, widths[2])

        return constraints.rstrip(",")

    def create_ties_str(self):
        """Returns the string of ties for this Fit
        """

        ties = ""
        # Widths
        for index, mass_info in enumerate(self.masses):
            func_index = index
            par_value_prefix = "f%d." % (func_index)
            par_name = "%sWidth" % par_value_prefix
            widths = mass_info['widths']
            if not hasattr(widths, "__len__"):
                # Fixed width
                ties += "%s=%f," % (par_name,widths)

            func_type = mass_info['function']
            if func_type == "GramCharlier":
                if 'k_free' not in mass_info:
                    raise RuntimeError("GramCharlier requested for mass %d but no k_free argument was found" % (index+1))
                k_free = mass_info['k_free']
                ## FSE constraint
                if k_free:
                    continue

                if 'sears_flag' not in mass_info:
                    raise RuntimeError("Fixed k requested for mass %d but no sears_flag argument was found" % (index+1))
                sears_flag = mass_info['sears_flag']
                par_name = "%sFSECoeff" % par_value_prefix
                if sears_flag == 1:
                    value = "%sWidth*%s" % (par_value_prefix,"sqrt(2)/12")#math.sqrt(2.)/12.0)
                else:
                    value = "0"
                ties += "%s=%s," % (par_name, value)

        return ties.rstrip(",")

    def create_global_function_str(self, n, param_values=None):
        """
            Creates the function string to pass to fit for a multi-dataset (global) fitting

            @param n :: A number of datasets (spectra) to be fitted simultaneously.

            @param param_values :: A dict/tableworkspace of key/values specifying the parameter values
            that have already been calculated. If None then the ComptonScatteringCountRate
            function, along with the constraints matrix, is used rather than the standard CompositeFunction.
            It is assumed that the standard CompositeFunction is used when running the fit for a
            second time to compute the errors with everything free
        """

        # create a local function to fit a single spectrum
        f = self.create_function_str(param_values)
        # insert an attribute telling the function which spectrum it should be applied to
        i = f.index(';')
        # $domains=i means "function index == workspace index"
        fun_str = f[:i] + ',$domains=i' + f[i:]

        # append the constrints and ties within the local function
        fun_str += ';constraints=(' + self.create_constraints_str() + ')'
        ties = self.create_ties_str()
        if len(ties) > 0:
            fun_str += ';ties=(' + ties + ')'

        # initialize a string for composing the global ties
        global_ties = 'f0.f0.Width'
        # build the multi-dataset function by joining local functions of the same type
        global_fun_str = 'composite=MultiDomainFunction'
        for i in range(n):
            global_fun_str += ';(' + fun_str + ')'
            if i > 0:
                global_ties = 'f' + str(i) + '.f0.Width=' + global_ties
        # add the global ties
        global_fun_str += ';ties=(' + global_ties + ')'

        return global_fun_str

    def __str__(self):
        """Returns a string representation of the object
        """
        self.generate_function_str()