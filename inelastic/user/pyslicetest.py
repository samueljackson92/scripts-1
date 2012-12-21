execfile('PySlice2.py')

from qtiGenie import *
inst='mar'
iliad_setup(inst)
ext='.raw'
mapfile='mari_res'
#det_cal_file must be specified if the reduction sends out put to a workpsace
cal_file='MAR16637.raw'
#load vanadium file
whitebeamfile="16637"
LoadRaw(Filename=whitebeamfile,OutputWorkspace="wb_wksp",LoadLogFiles="0")
#---------------------------------------------------------------------------------------------------------------
#---------------------------------------------------------------------------------------------------------------
ei=100
rebin_params='-10,.2,95'
#load run
#runfile="16644"

runfile=[16654]
#16642,16643,16644,16645,16648,16649,16652]
#save .spe file

save_file=inst+str(runfile)+'_norm.spe'
LoadRaw(Filename=runfile,OutputWorkspace="run_wksp",LoadLogFiles="0")
	#w1=iliad("wb_wksp","run_wksp",ei,rebin_params,mapfile,det_cal_file=cal_file,norm_method ='current')
w1=iliad("wb_wksp","run_wksp",ei,rebin_params,mapfile,det_cal_file=cal_file,norm_method='current',diag_sigma=3,mask_run=16654)


runfile=[16643]

save_file=inst+str(runfile)+'_norm.spe'
LoadRaw(Filename=runfile,OutputWorkspace="run_wksp",LoadLogFiles="0")
	#w1=iliad("wb_wksp","run_wksp",ei,rebin_params,mapfile,det_cal_file=cal_file,norm_method ='current')
w2=iliad("wb_wksp","run_wksp",ei,rebin_params,mapfile,det_cal_file=cal_file,norm_method='current',diag_sigma=3,mask_run=16654)


w1=mtd['w1']
w2=mtd['w2']
ww=data2D(w1)

www=data2D(w2)

ww.rebinproj('0,.1,12',fast=True)
www.rebinproj('0,.1,12',fast=True)
ww.display(10)
ww.CutAlongE(1,5,-10,1,80)
ww.CutAlongE(1,10,-10,1,80,over=True)
www.CutAlongE(1,10,-10,1,80,over=True)
ww.CutAlongQ(-10,10,0,.2,12)
ww.CutAlongQ(15,30,0,.2,12,over=True)
ww.XaxisLims(3,6)