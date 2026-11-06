#!/usr/bin/env python3
"""Reproducible ideal-circuit bounds, deliberately separate from hardware tests."""
from pathlib import Path
import itertools,json,math
ROOT=Path(__file__).resolve().parents[1]

def main():
    results={}
    vals=[10e6,10e6,82e3,82e3,82e3,82e3,330,1000]
    for cv in [-5,0,5]:
        values=[];pre=[]
        for signs in itertools.product([.99,1.01],repeat=8):
            r=[a*b for a,b in zip(vals,signs)]
            for vdd in [3.0,3.6]:
                sensed=cv*r[1]/(r[0]+r[1])
                a=(sensed/r[2]+vdd/r[3]+vdd/r[4])/(1/r[2]+1/r[3]+1/r[4]+1/r[5])
                adc=a*r[7]/(r[6]+r[7]);values.append(adc);pre.append(a)
        results[str(cv)]={'ADC_V_min':min(values),'ADC_V_max':max(values),'C13_precharge_V_min':min(pre),'C13_precharge_V_max':max(pre),'nominal_ADC_V_at_3V3':(3.3/2+cv/8)*100/133}
    vcapmax=max(x['C13_precharge_V_max'] for x in results.values())
    r3min=82000*.99;r7min=1000*.99;r25max=1000*1.01
    ilim={'min_mA':25230/(68*1.01)**1.016,'nominal_mA':23950/68**.977,'max_mA':22980/(68*.99)**.94}
    buck=[]
    for label,vin,vout,l,fs in [('nominal',12,5,4.7e-6,1.1e6),('specified_component_corner',13.2,5.05,4.7e-6*.8,1.1e6*.94)]:
        dI=vout*(vin-vout)/(vin*l*fs)
        buck.append({'case':label,'Vin_V':vin,'Vout_V':vout,'L_H':l,'switching_Hz':fs,'CCM_ripple_A':dI,'peak_A_at_0p4A_load':.4+dI/2,'RMS_A_at_0p4A_load':math.sqrt(.4**2+dI**2/12)})
    rho=1.724e-8;cu=35e-6
    bridge_loop_R=rho/cu*((.0495+.0495+2*(2*math.sqrt(.0011**2+.0011**2)-.0022))/.0005+(.0099+.0151)/.00035)
    bridge_I=ilim['max_mA']/1000
    out={'revision':'A5','scope':'Ideal resistor/steady-DC calculations, not simulation of semiconductor fault states or a hardware qualification',
     'cv_transfer':{'formula':'VADC=(100/133)*(VDD/2+CV/8)','inverse':'CV=10.64*VADC-4*VDD','input_impedance_ohm_nominal':20e6,'resistor_corners':256,'supply_cases_V':[3.0,3.6],'corners_per_CV':512,'results':results,'excluded':'Op-amp offset/bias/gain error, ADC/reference error, PCB leakage, temperature coefficient and ageing'},
     'C13_upstream_of_R7':{'C13_net':'CV_AFFINE','R7_from':'CV_AFFINE','R7_to':'CV_FILTER','U7_IN_plus_net':'CV_FILTER','nominal_filter_Rth_ohm':82000/4,'nominal_pole_Hz':1/(2*math.pi*(82000/4)*10e-9),'normal_precharge_max_V':vcapmax,'R7_min_ohm':r7min,'conditional_peak_input_path_current_A':(vcapmax+.5)/r7min,'condition':'CV within +/-5V, VDD initially3.0..3.6V, resistor corners above; receiving node no lower than-0.5V; no other stored/transient source. This is not a proof of U7 differential input limits or all collapse states.'},
     'conditional_fully_off_DC':{'assumed_CV_BUF_abs_limit_V':20,'R3_min_ohm':r3min,'R7_min_ohm':r7min,'R25_max_ohm':r25max,'only_feed_current_A_conservative':20/r3min,'ADC_abs_bound_V_conservative':20/r3min*r25max,'with_R7_included_ADC_abs_bound_V':20/(r3min+r7min)*r25max,'scope':'Steady DC with no other energy feeding ADC/3V3, all input current pessimistically assigned to R25 or the1k3V3bleeder. Does not assume an unpowered U7 output specification. No proof for partial rails, differential-input absolute maximum, capacitor energy, supply reverse current, ESD, overshoot or damaged components.'},
     'TPS2552_1_RILIM_68k_1percent':ilim,
     'dual_stream_leaf_bridge':{'controller_pinout':{'1':'GND','2':'VLED','3':'DATA_L','4':'DATA_R'},'leaf_J1_pinout':{'1':'GND','2':'VLED','3':'DATA_IN','4':'DATA_OTHER'},'leaf_J2_pinout':{'1':'GND','2':'VLED','3':'DATA_OTHER','4':'DATA_IN'},'cables':'Two completed straight1:1 Adafruit4399 cables; controllerJ3→leftJ1, leftJ2→rightJ1. RightJ2 unconnected externally.','JST_SH_rating_A_with_AWG28':1.0,'TPS_max_A':bridge_I,'current_rating_ratio':1/bridge_I,'assumed_copper_thickness_m':cu,'assumed_copper_resistivity_ohm_m':rho,'PCB_bridge_loop_R_ohm_at_reference_temperature':bridge_loop_R,'PCB_bridge_loop_drop_V_at_TPS_max':bridge_loop_R*bridge_I,'PCB_bridge_loop_loss_W_at_TPS_max':bridge_loop_R*bridge_I**2,'scope':'Conservative full current through both first-leaf rails including connector branches,0.5mm rails/0.35mm branches,ideal35um copper. Excludes contact/cable resistance, plating variation, temperature rise and dynamic droop. The first cable carries both leaves. The linked Adafruit drawing specifiesAWG28; actual delivered wire/contact construction remains an incoming-lot gate.'},
     'buck_4p7uH':{'cases':buck,'limitations':'CCM estimates. Low-load PFM, startup, current-limit/hot-short, core bias/loss, DC-bias capacitance, layout and actual temperature are not validated. TDK3.5AIsat and2.5Athermal are typical; AP63205 peak limit3.1Amaximum is not a guaranteed hot-core design margin.'},
     'switch_underbody_nominal_gap_mm':1.5-.55,
     'hardware_tests':'NOT_RUN'}
    (ROOT/'reports'/'electrical_margins.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'CV5_nominal_ADC':results['5']['nominal_ADC_V_at_3V3'],'filter_Hz':out['C13_upstream_of_R7']['nominal_pole_Hz'],'C13_path_mA':out['C13_upstream_of_R7']['conditional_peak_input_path_current_A']*1000,'off_DC_bound_V':out['conditional_fully_off_DC']['ADC_abs_bound_V_conservative'],'ILIM_mA':ilim},indent=2))
if __name__=='__main__':main()
