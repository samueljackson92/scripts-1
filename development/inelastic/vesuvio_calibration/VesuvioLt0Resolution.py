#pylint: disable=no-init

from mantid.kernel import *
from mantid.api import *
from mantid.simpleapi import *

import numpy as np

BACKSCATTERING = range(3, 135)
FORWARDSCATTERING = range(135, 199)

U_PEAKS = [
#    Er      dEr    vr          t      dTr
#    meV     meV    m/usec      usec   usec
    [36684., 133.6, 83768.0e-6, 131.  ,0.24],
    [20874., 91.7,  63190.0e-6, 173.8 ,0.38],
    [6672.,  52.4,  35725.0e-6, 307.7 ,1.21]
]

#----------------------------------------------------------------------------------------

class VesuvioLt0Resolution(PythonAlgorithm):

    def summary(self):
        return "Calculates the resolution of the total flight path and t0 for VESUVIO."

    def PyInit(self):
        # Input parameter tables
        self.declareProperty(WorkspaceGroupProperty("ParametersT0", "", Direction.Input),
                             doc="Peak parameters fitted for t0 in EVSCalibrationAnalysis")
        self.declareProperty(WorkspaceGroupProperty("ParametersL0", "", Direction.Input),
                             doc="Peak parameters fitted for L0 in EVSCalibrationAnalysis")

        # Output parameter tables
        self.declareProperty(ITableWorkspaceProperty("ForwardParameters", "", Direction.Output),
                             doc="Resolution values for forward scattering")
        self.declareProperty(ITableWorkspaceProperty("BackParameters", "", Direction.Output),
                             doc="Resolution parameters for backscattering")

        # Mean total flight path (L)
        self.declareProperty("MeanForwardL", 0.0, direction=Direction.Output,
                             doc="Mean total flight path length for forward scattering (m)")
        self.declareProperty("MeanBackL", 0.0, direction=Direction.Output,
                             doc="Mean total flight path length for backscattering (m)")

        # Mean t0
        self.declareProperty("MeanForwardT0", 0.0, direction=Direction.Output,
                             doc="Mean t0 for forward scattering (uSec)")
        self.declareProperty("MeanBackT0", 0.0, direction=Direction.Output,
                             doc="Mean t0 for backscattering (uSec)")

#----------------------------------------------------------------------------------------

    def PyExec(self):
        t0_peak_params = mtd[self.getPropertyValue("ParametersT0")]
        l0_peak_params = mtd[self.getPropertyValue("ParametersL0")]

        back_fit_params = self._calculate(BACKSCATTERING, t0_peak_params, 11.005)
        forward_fit_params = self._calculate(FORWARDSCATTERING, l0_peak_params, 11.005)

        back_params = CreateEmptyTableWorkspace(OutputWorkspace=self.getPropertyValue("BackParameters"))
        forward_params = CreateEmptyTableWorkspace(OutputWorkspace=self.getPropertyValue("ForwardParameters"))
        self._add_output_columns(back_params, back_fit_params)
        self._add_output_columns(forward_params, forward_fit_params)

        self.setProperty("BackParameters", back_params)
        self.setProperty("ForwardParameters", forward_params)

        back_l_data = back_params.column('L')
        back_t0_data = back_params.column('t0')
        forward_l_data = forward_params.column('L')
        forward_t0_data = forward_params.column('t0')

        self.setProperty("MeanBackL", np.mean(back_l_data[back_l_data != 0]))
        self.setProperty("MeanBackT0", np.mean(back_t0_data[back_t0_data != 0]))
        self.setProperty("MeanForwardL", np.mean(forward_l_data[forward_l_data != 0]))
        self.setProperty("MeanForwardT0", np.mean(forward_t0_data[forward_t0_data != 0]))

#----------------------------------------------------------------------------------------

    def _calculate(self, detectors, calibration_params, l0_dist):
        wks = WorkspaceFactory.Instance().create('Workspace2D', len(detectors), 3, 3)
        for detector in detectors:
            det_index = detector - detectors[0]

            x_data = []
            for peak in range(3):
                peak_position = calibration_params.getItem(peak).column('f1.PeakCentre')[det_index]
                x_data.append(1.0/(l0_dist/peak_position )**2)

                params = calibration_params.getItem(peak)
                sigma = params.column('f1.Sigma')[det_index]
                sigma_err = params.column('f1.Sigma_Err')[det_index]

                u_peak = U_PEAKS[peak]
                wks.dataY(det_index)[peak] = (sigma ** 2) - (u_peak[4]**2)
                wks.dataE(det_index)[peak] = 2*sigma*sigma_err

            wks.setX(det_index, np.array(x_data))

        AnalysisDataService.Instance().addOrReplace('__bank_data', wks)

        fit = AlgorithmManager.Instance().create('PlotPeakByLogValue')
        fit.initialize()
        fit.setChild(True)
        fit.setProperty('Function', 'name=LinearBackground')
        fit.setProperty('Input', '__bank_data,v0:132')
        fit.setProperty('OutputWorkspace', 'backscattering_params')
        fit.execute()

        DeleteWorkspace('__bank_data')

        params = fit.getProperty('OutputWorkspace').value
        for index, detector in enumerate(detectors):
            params.setCell(index, 0, detector)

            t0 = params.cell(index, 1)
            l_dist = params.cell(index, 3)

            if t0 > 0:
                t0 = np.sqrt(t0)
            else:
                t0 = 0

            if l_dist > 0:
                l_dist = np.sqrt(l_dist)
            else:
                l_dist = 0

            params.setCell(index, 1, t0)
            params.setCell(index, 3, l_dist)

        return params

#----------------------------------------------------------------------------------------

    def _add_output_columns(self, table, fit_table):
        table.addColumn('float', 'Detector')
        table.addColumn('float', 't0')
        table.addColumn('float', 't0_Err')
        table.addColumn('float', 'L')
        table.addColumn('float', 'L_Err')

        for row_idx in range(fit_table.rowCount()):
            old_row = fit_table.row(row_idx)
            table.addRow([old_row['axis-1'], old_row['A0'], old_row['A0_Err'], old_row['A1'], old_row['A1_Err']])

#----------------------------------------------------------------------------------------

AlgorithmFactory.subscribe(VesuvioLt0Resolution)
