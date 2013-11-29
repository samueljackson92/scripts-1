##
## Just helpers for now to keep alot of the unimportant details out of the way
## This will all be refactored when it gets incorporated properly
##
import math
import numpy as np
import types

#----------------------------------------------------------------------------------------
def preprocess(data_ws, options):
    """Runs a set of preprocessing steps on the workspace
    before fitting based on the given options
    @param data_ws :: The workspace containing the data to process
    @param fit_options :: An object of type FitOptions containing
                          the required parameters
    @returns The result workspace
    """
    print "-- Preprocessing --"
    if options.has_been_set("smooth_points"):
        pts = options.smooth_points
        if pts > 0:
            print "Smoothing data using %d neighbours" % pts
            from mantid.simpleapi import SmoothData
            data_ws = SmoothData(InputWorkspace=data_ws, OutputWorkspace=data_ws, NPoints=[pts])
        else:
            raise ValueError("Invalid number of points for smoothing: '%d'."
                             " Value must be greater than zero. Set to None to turn off smoothing" % pts)

    if options.has_been_set("bad_data_error"):
        mask_data(data_ws, options.bad_data_error)
        
    return data_ws

#----------------------------------------------------------------------------------------

def mask_data(workspace, error_threshold, verbose=False):
    """
        Masks data points on the workspace that have an error above
        the given error threshold
        @param workspace :: The workspace containing the data. The mask will occur place
        @param error_threshold :: Above this value, the data point will be masked
                                  using MaskBins
        @param verbose :: If true then each bin that is masked is printed to the screen
    """
    from mantid.simpleapi import MaskBins
    print "Masking data with errors > %f" % error_threshold

    # The data shouldn't be too big, clone it to numpy and use its search capabilities
    errors = workspace.extractE()
    if len(errors.shape) != 2:
        raise RuntimeError("Expected 2D array of errors, found %dD" % len(errors.shape))

    indices = np.where(errors > error_threshold) # Indices in 2D matrix where errors above threshold
    # The output is a tuple of 2 arrays where the indices from each array are paired to 
    # give the correct inndex in the original 2D array.
    x_data = workspace.readX(0)

    for ws_index, bin_index in zip(indices[0],indices[1]):
        xmin, xmax = x_data[bin_index],x_data[bin_index+1]
        if verbose:
            print "Masking index %d between [%f,%f]" % (ws_index,xmin,xmax)
            MaskBins(InputWorkspace=workspace, SpectraList=[int(ws_index)],
                     XMin=xmin,XMax=xmax)

#----------------------------------------------------------------------------------------
def run_simulation(data_ws, fit_options):
    """
        Run the Fit algorithm with a single iteration with the given options on the input data
        @param data_ws :: The workspace containing the data to fit too
        @param fit_options :: An object of type FitOptions containing
                              the parameters 
    """
    return _run_fit_impl(data_ws, fit_options, simulation=True)
    
#----------------------------------------------------------------------------------------

def run_fit(data_ws, fit_options):
    """
        Run the Fit algorithm with the given options on the input data
        @param data_ws :: The workspace containing the data to fit too
        @param fit_options :: An object of type FitOptions containing
                              the parameters 
    """
    return _run_fit_impl(data_ws, fit_options, simulation=False)

#----------------------------------------------------------------------------------------

def _run_fit_impl(data_ws, fit_options, simulation=False):
    """
        Run the Fit algorithm with the given options on the input data
        @param data_ws :: The workspace containing the data to fit too
        @param fit_options :: An object of type FitOptions containing
                              the parameters
        @param simulation :: If true then only a single iteration is run
    """
    from mantid.simpleapi import RenameWorkspace, mtd

    if simulation:
        print "-- Simulation Options Summary --"
    else:
        print "-- Fitting Options Summary --"

    for mass_index, mass_info in enumerate(fit_options.masses):
        display = "Mass %d: %s"
        if mass_info['function'] == "GramCharlier":
            c_free = mass_info['hermite_coeffs']
            terms = ""
            for c_index, value in enumerate(c_free):
                if value == 1:
                    terms += "H_%d " % (2*c_index)
            if simulation:
                details = "GramCharlier, Hermite Terms='%s'" % terms.rstrip()
                if 'KFSECoeff' in mass_info:
                    details += ", Kfse=%f" % (mass_info['KFSECoeff'])
            else:
                details = "GramCharlier, Hermite Terms='%s', Sears Flag=%d" % (terms.rstrip(), mass_info['sears_flag'])
        else:
            details = "Gaussian"
        display =  display % (mass_index+1,details)
        print display
    if fit_options.has_been_set("background_order"):
        print "Including background using polynomial of order=%d" % fit_options.background_order

    if simulation:
        # Just set what we have been given
        param_values = fit_options.create_param_table()
        constraints=None
        ties=None
    else:
        #### Run fitting first time using constraints matrix to reduce active parameter set ######
        function_str = fit_options.create_function_str()
        constraints = fit_options.create_constraints_str()
        ties = fit_options.create_ties_str()
        _do_fit(function_str, data_ws, constraints, ties, max_iter=5000)
    
        #### Run fitting first time using constraints matrix to reduce active parameter set ######
        params_ws = mtd["__fit_Parameters"]
        param_values = {}
        for row in params_ws:
            values = row.values()
            param_values[values[0]] = values[1]

    function_str = fit_options.create_function_str(param_values)
    max_iter = 0 if simulation else 1
    reduced_chi_square = _do_fit(function_str, data_ws, constraints, ties, max_iter=max_iter)

    ws_prefix = "__fit"
    fit_suffixes = ('_Parameters','_NormalisedCovarianceMatrix','_Workspace')
    for suffix in fit_suffixes:
        RenameWorkspace(InputWorkspace=ws_prefix + suffix,OutputWorkspace="fit" + suffix)
    
    return reduced_chi_square, mtd["fit_Parameters"]

def _do_fit(function_str, data_ws, constraints, ties, max_iter):
    from mantid.simpleapi import Fit, ScaleX

    ScaleX(InputWorkspace=data_ws,OutputWorkspace=data_ws,Operation='Multiply',Factor=1e-06)

    results = Fit(function_str,data_ws,Ties=ties,Constraints=constraints,Output="__fit",
                  CreateOutput=True,OutputCompositeMembers=True,MaxIterations=max_iter, 
                  Minimizer="Levenberg-Marquardt,AbsError=1e-08,RelError=1e-08")
    
    ScaleX(InputWorkspace='__fit_Workspace',OutputWorkspace='__fit_Workspace',Operation='Multiply',Factor=1e06)
    ScaleX(InputWorkspace=data_ws,OutputWorkspace=data_ws,Operation='Multiply',Factor=1e06)
    
    return results[1] # reduced chi-squared

#----------------------------------------------------------------------------------------
class FitOptions(object):
    """Holds all of the parameters for the reduction & fit"""

    # Main options
    _options = {}
    # Defaults
    _defaults = {}
    
    def __init__(self):
        options = {
          "smooth_points":None,
          "bad_data_error":None,
          "background_function":None,
          "background_order":None,
          "masses" : None,
          "constraints":None,
          "workspace_index":None,
          "output_prefix":None
        }
        object.__setattr__(self, "_options", options)
        defaults = {
            "background_function":"Polynomial"
        }
        object.__setattr__(self, "_defaults", defaults)

    def has_been_set(self, name):
        """Returns true if the given option has been set by the user
        """
        return self.__getattr__(name) is not None

    def validate_options(self):
        """Checks that the current options
        are consistent"""
        pass
    
    def create_param_table(self):
        """Returns a dictionary of parameters that can be used
        to simulate a fit
        @todo cut down copy-and-paste here!
        """
        
        param_values = {}
        for index, mass_info in enumerate(self.masses):
            par_value_prefix = "f%d." % (index)

            widths = mass_info['widths']
            if hasattr(widths, "__len__"):
                width = widths[1]
            else:
                width = widths
            param_values[par_value_prefix + "Width"] = width

            func_type = mass_info['function']
            if func_type == "GramCharlier":
                if 'FSECoeff' in mass_info:
                    fse = mass_info['FSECoeff']
                else:
                    fse = 0
                param_values[par_value_prefix + "FSECoeff"] = fse
                hermite = mass_info['hermite_coeffs']
                for i,c in enumerate(hermite):
                    if c != 0:
                        param_values["%sC_%d" % (par_value_prefix,2*i)] = c
            elif func_type == "Gaussian":
                param_values[par_value_prefix + "Intensity"] = mass_info["Intensity"]

        return param_values

#-------------------------------------------------------------------------------------------------------------        

    def create_function_str(self, param_values=None):
        """
            Creates the function string to pass to fit
        
            @param param_values :: A dict of key/values specifying the parameter values
            that have already been calculated. If None then the ComptonScatteringCountRate
            function, along with the constraints matrix, is used rather than the standard CompositeFunction.
            It is assumed that the standard CompositeFunction is used when running the fit for a
            second time to compute the errors with everything free
        """
        all_free = (param_values is not None)
        
        if all_free:
            function_str = "composite=CompositeFunction,NumDeriv=1;"
        else:
            function_str = "composite=ComptonScatteringCountRate,NumDeriv=1%s;"
            matrix_str = self.create_matrix_string(self.constraints)
            if matrix_str == "":
                function_str = function_str % ""
            else:
                function_str = function_str % (",IntensityConstraints=" + matrix_str)

        for index, mass_info in enumerate(self.masses):
            par_value_prefix = "f%d." % (index)
            try:
                func_type = mass_info['function']
            except KeyError:
                raise RuntimeError("Mass details does not contain a function definition")

            if func_type == "GramCharlier":
                local_function_str = \
                    self.create_gram_charlier_function(mass_info, all_free, param_values, par_value_prefix)
            elif func_type == "Gaussian":
                func_name = "GaussianComptonProfile"
                mass = mass_info['value']
                if all_free:
                    width = param_values[par_value_prefix + "Width"]
                else:
                    widths = mass_info['widths']
                    if hasattr(widths, "__len__"):
                        width = widths[1]
                    else:
                        width = widths

                params = "WorkspaceIndex=%d,Mass=%f,Width=%f" % (self.workspace_index,mass,width)
                if all_free:
                    par_name = "Intensity"
                    params += ",%s=%f" % (par_name,param_values[par_value_prefix + par_name])
                local_function_str = "name=%s,%s;" % (func_name,params)
            else:
                raise ValueError("Unknown function type: '%s'. Allowed values are: GramCharlier, Gaussian")
            function_str += local_function_str

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
                    par_name = 'A%d' % (power)
                    comp_par_name = 'f%d.%s' % (func_index,par_name)
                    background_str += ",%s=%f" % (par_name,param_values[comp_par_name])
            function_str += "%s" % background_str.rstrip(",")
        
        return function_str.rstrip(";")

    def create_gram_charlier_function(self, mass_info, all_free, param_values, par_value_prefix):
        """
        Adds a GramCharlierComptonProfile to the function str and returns
        the updated version
        @param mass_info Dictionary of mass details
        @param all_free True if all should be left free and initial parameters set (see param_values)
        @param values Dictionary of named parameter values from a previous fit
        @param par_value_prefix The prefix within the composite for this function, i.e f0.
        @returns the function string
        """
        func_name = "GramCharlierComptonProfile"
        mass = mass_info['value']
        if all_free:
            width = param_values[par_value_prefix + "Width"]
        else:
            widths = mass_info['widths']
            if hasattr(widths, "__len__"):
                width = widths[1]
            else:
                width = widths

        def to_space_sep_str(collection):
            _str = ""
            for item in collection:
                _str += " " + str(item)
            return _str.lstrip()
        hermite_coeffs = mass_info['hermite_coeffs']
        hermite_str = to_space_sep_str(hermite_coeffs)

        params = "WorkspaceIndex=%d,Mass=%f,HermiteCoeffs=%s,Width=%f" \
          % (self.workspace_index,mass,hermite_str,width)
        if all_free:
            par_names = ["FSECoeff"]
            for i,c in enumerate(hermite_coeffs):
                if c > 0:
                    par_names.append("C_%d" % (2*i))
            for par_name in par_names:
                params += ",%s=%f" % (par_name,param_values[par_value_prefix + par_name])

        return "name=%s,%s;" % (func_name, params)

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
                    value = "%sWidth*sqrt(2)/12" % par_value_prefix
                else:
                    value = "0"
                ties += "%s=%s," % (par_name, value)

        return ties.rstrip(",")

    def __setattr__(self, name, value):
        """Only allows those attributes that we have defined. 
        Raises a AttributeError if the name is unknown
        """
        if name in self._options:
            # Make sure the constraints tuple is still a tuple
            # If first element looks like sequence we have more than 1 constraint
            # or the tuple was created with a trailing comma and is 1 in size.
            # If the first element is not a sequence a single-element tuple was created without a 
            # trailing comma so the tuple was stripped
            if name == "constraints" and (value is not None) \
                    and (len(value) > 0 and not hasattr(value[0], "__len")):
                    value = (value,) # note trailing comma
            self._options[name] = value
        else:
            raise AttributeError("Unknown attribute %s. "
                            "Allowed names (%s)" % (name, str(self._options.keys())))


            
    def __getattr__(self, name):
        """Return the named attribute's value.
        Raises a NameError if the name is unknown
        """
        try:
            return self._options[name]
        except KeyError:
            raise AttributeError("Unknown attribute %s. "
                            "Allowed names (%s)" % (name, str(self._options.keys())))
            
    def __str__(self):
        """Returns a string representation of the object
        """
        self.generate_function_str()
    
#----------------------------------------------------------------------------------------

def display_fit_output(reduced_chi_square, params_ws, fit_options):
    nmasses = len(fit_options.masses)
    
    # Widths
    wg_best = []
    del_wg_best = []
    # Peak areas
    Av_best = []
    del_Av_best = []
    # Expansion coefficents for protons
    c_best = {}
    del_c_best = {}
    # FSE term
    k_best = {}
    del_k_best = {}
    # Background
    bkgd = []
    d_bkgd = []

    for row in params_ws:
        name,value,error = row.values()
        if "C_" in name:
            findex = int(name[1])
            if len(c_best) == findex:
                c_best[findex] = []
                del_c_best[findex] = []
            c_best[findex].append(value)
            del_c_best[findex].append(error)
        if "C_0" in name or "Intensity" in name:
            Av_best.append(value)
            del_Av_best.append(error)
        elif 'Width' in name:
            wg_best.append(value)
            del_wg_best.append(error)
        elif 'FSE' in name:
            findex = int(name[1])
            k_best[findex] = value
            del_k_best[findex] = error
        elif '.A' in name:
            bkgd.append(value)
            d_bkgd.append(error)

    # Fill in zeroes for non-active hermite coeffs
    for index, mass_info in enumerate(fit_options.masses):
        if 'hermite_coeffs' not in mass_info:
            continue
        nc = len(mass_info['hermite_coeffs'])
        n_active_c = len(c_best[index])
        if nc > n_active_c:
            for i in range(n_active_c,nc):
                c_best[index].append(0.0)
                del_c_best[index].append(0.0)
    
    #######################################
    # Peak areas are normalized to the sum
    #######################################
    Av_best = np.array(Av_best)
    Av_best_sum = np.sum(Av_best)
    Av_best_norm = Av_best/Av_best_sum
    del_Av_best_norm = []
    
    # Errors by full differential
    jacobian = np.empty(shape=(nmasses,nmasses))
    for j in range(nmasses):
        for k in range(nmasses):
            epsilon_k = del_Av_best[k]
            if k == j:
                df_j_k_r = (Av_best[k]+0.01*Av_best[k])/(Av_best_sum+0.01*Av_best[k])
                df_j_k_l = (Av_best[k]-0.01*Av_best[k])/(Av_best_sum-0.01*Av_best[k])
            else:
                df_j_k_r = Av_best[k]/(Av_best_sum+0.01*Av_best[k])
                df_j_k_l = Av_best[k]/(Av_best_sum-0.01*Av_best[k])
                
            jacobian[j][k] = (df_j_k_r - df_j_k_l)/epsilon_k
    
    for j in range(nmasses):
        del_Av_best_norm_j = 0.0 
        for k in range(nmasses):
            df_j_k = jacobian[j][k]
            Av_best_k = Av_best[k]
            del_Av_best_k = del_Av_best[k]
            del_Av_best_norm_j += (df_j_k*del_Av_best_k)**2
    
        del_Av_best_norm.append(math.sqrt(del_Av_best_norm_j))
    
    ##########################################
    # Expansion coefficients normalized to C_0
    ##########################################
    # Insert zeroes for those that are off
    # and compute reduced coefficients
    a_best = {}
    del_a_best = {}
    
    for func_index in c_best.keys():
        a_best[func_index] = []
        del_a_best[func_index] = []
        
        c0 = c_best[func_index][0]
        dc0 = del_c_best[func_index][0]
        if c0 == 0.0: 
            c0 = 1
    
        if func_index in k_best:
            try:
                k_free = fit_options.masses[func_index]['k_free']
            except KeyError:
                k_free = False
            if k_free:
                del_k_best[func_index] = math.fabs(del_k_best[func_index]*c0 - dc0*k_best[func_index])/c0/c0
                k_best[func_index] = k_best[func_index]/c0
            else:
                del_k_best[func_index] = del_wg_best[func_index]*math.sqrt(2)/12
    
        # Normalise expansion coefficients
        hermite_coeffs = fit_options.masses[func_index]['hermite_coeffs']
        for index, flag in enumerate(hermite_coeffs):
            c_i  = c_best[func_index][index]
            dc_i = del_c_best[func_index][index]

            del_c_best[func_index][index] = math.fabs(dc_i*c0 - dc0*c_i)/c0/c0
            c_best[func_index][index] /= c0
            npoly = 2*index
            denom = (2**npoly)*math.factorial(index)
            a_best[func_index].append(c_best[func_index][index]/denom)
            del_a_best[func_index].append(del_c_best[func_index][index]/denom)
    
    ######################################
    # Display
    ######################################
    message = None
    
    message = "\n"
    message += '\nReduced Chi-Square =%f\n\n' % reduced_chi_square
    message += 'Fitting in the TOF space\n'
    
    for i in range(nmasses):
        mass_info = fit_options.masses[i]
        message += '-'*80 + "\n"
    
        message += 'The mass M(%d)=%f\n\n' % (i+1,mass_info['value'])
        
        message += 'Parameters values in the Y space:\n\n'
        
    
        # --- Currently on displayed in the results log as we can't yet pull them from Fit ---
        message += 'See results log for resolution parameters w_L1, w_L0 etc\n'
        # disp(['w_L_1 (FWHM)= ',num2str(w_L1(:,i))])
        # disp(['w_L_0 (FWHM)= ',num2str(w_L0(:,i))])
        # disp(['w_T_h_e_t_a (FWHM)= ',num2str(w_theta(:,i))])
        # disp(['w_F_o_i_l_L_o_r_e_n_t_z (FWHM)= ',num2str(wl(:,i))])
        # disp(['w_F_o_i_l_G_A_U_S_S (FWHM) = ',num2str(wE_gauss(:,i))])
        
        message += 'St. dev. of momentum distr. = %f +/- %f\n' % (wg_best[i],del_wg_best[i])
        message += 'Scatt. int. (area, normalised) = %f +/- %f\n' % (Av_best_norm[i],del_Av_best_norm[i])
        
        if mass_info['function'] == 'GramCharlier': # First mass
            nc = len(mass_info['hermite_coeffs'])
            for u in range(nc):
                message += 'Hermite polynomial expansion coefficient c%d = %f +/- %f\n' % (2*u,c_best[i][u],del_c_best[i][u])
      
            for u in range(nc):
                message += 'Hermite polynomial expansion coefficient a%d = c%d/(2^%d*%d!) = %f +/ %f\n' % (2*u,2*u,2*u,u,a_best[i][u],del_a_best[i][u])
    
            message += '\nFSE coefficient k by the k/q He_3(y) expansion member = %f +/- %f\n\n' % (k_best[i], del_k_best[i])
            message += 'The coefficient k calculated in a harmonic oscillator model would be k = sigma*sqrt(2)/12 = %f\n\n' % (wg_best[i]*math.sqrt(2)/12)
        

    if fit_options.has_been_set("background_order"):
        message += '-'*80 + "\n"
        message += 'Background was fitted with the polynomial of degree %d:\n' % fit_options.background_order
        counter = fit_options.background_order
        for coeff,error in reversed(zip(bkgd,d_bkgd)):
            message += 'Polynomial coefficient order %d: %f +/- %f\n' % (counter, coeff, error)
            counter -= 1
        message += '-'*80 + "\n"
        
    print message
    return message
