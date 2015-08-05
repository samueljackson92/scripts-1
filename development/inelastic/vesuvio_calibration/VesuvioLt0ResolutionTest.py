#pylint: disable=too-many-public-methods

import unittest

from mantid.api import ITableWorkspace
from mantid.simpleapi import *


class EVSCalibrationTest(unittest.TestCase):

    def setUp(self):
        self._t0_params = Load(Filename='cal_Iteration_0_t0_Peak_Parameters.nxs',
                               OutputWorkspace='__evs_calib_t0_params')

        self._l0_params = Load(Filename='cal_Iteration_0_L0_Peak_Parameters.nxs',
                               OutputWorkspace='__evs_calib_L0_params')


    def tearDown(self):
        mtd.clear()


    def _validate_result_shape(self, forward, back, mean):
        """
        Validates the shape of the result tables.
        """

        self.assertTrue(isinstance(forward, ITableWorkspace))
        self.assertEqual(forward.columnCount(), 5)
        self.assertEqual(forward.rowCount(), 64)

        self.assertTrue(isinstance(back, ITableWorkspace))
        self.assertEqual(back.columnCount(), 5)
        self.assertEqual(back.rowCount(), 132)

        self.assertTrue(isinstance(mean, ITableWorkspace))
        self.assertEqual(mean.rowCount(), 4)


    def test_run_no_par_file(self):
        """
        Tests running using default distances in IDF.
        """
        forward, back, mean = VesuvioLt0Resolution(ParametersT0=self._t0_params,
                                                   ParametersL0=self._l0_params)
        self._validate_result_shape(forward, back, mean)

        #TODO


    def test_run_with_par_file(self):
        """
        Tests running using distances from an instrument parameter file.
        """
        forward, back, mean = VesuvioLt0Resolution(ParametersT0=self._t0_params,
                                                   ParametersL0=self._l0_params,
                                                   InstrumentParFile='IP0005.par')
        self._validate_result_shape(forward, back, mean)

        #TODO


if __name__ == '__main__':
    unittest.main()
