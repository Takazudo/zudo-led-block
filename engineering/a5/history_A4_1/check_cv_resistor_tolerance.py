"""Corner calculation for the proposed 1% Basic-resistor CV sensing network.
This is an ideal DC resistor calculation, not SPICE or a hardware measurement.
"""
from itertools import product
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent

def calculate(cv, supply, errors):
    rtop, rbottom = [10e6 * (1 + e) for e in errors[:2]]
    rcv, rbias1, rbias2, rgnd = [82e3 * (1 + e) for e in errors[2:]]
    buffer = cv * rbottom / (rtop + rbottom)
    gs = [1/rcv, 1/rbias1, 1/rbias2, 1/rgnd]
    return (buffer * gs[0] + supply * (gs[1] + gs[2])) / sum(gs)

def main():
    cases = []
    for cv in [-12, -5, 0, 5, 12]:
        readings = [calculate(cv, v, e) for v in (3.3 * .98, 3.3 * 1.02)
                    for e in product([-.01, .01], repeat=6)]
        nominal_supply_readings = [calculate(cv, 3.3, e) for e in product([-.01, .01], repeat=6)]
        ratios = [calculate(cv, v, e) / v for v in (3.3 * .98, 3.3 * 1.02)
                  for e in product([-.01, .01], repeat=6)]
        errors = [(x - 1.65) * 8 - cv for x in nominal_supply_readings]
        cases.append({'CV_V':cv, 'nominal_ADC_V':1.65+cv/8,
                      'ADC_V_with_resistor_1pct_and_supply_2pct':[min(readings),max(readings)],
                      'ADC_fraction_of_its_supply':[min(ratios),max(ratios)],
                      'input_equivalent_resistor_error_at_3V3':[min(errors),max(errors)]})
    result = {'network':'10M/10M pickup, unity buffer,82k from buffer,2x82k to3V3,82k toGND',
              'tolerance':{'all_six_resistors':.01,'supply_assumption':.02},
              'cases':cases,
              'scope':'Independent exact extreme corners of nominal DC resistor network. Excludes ADC, reference, buffer offset/bias, clamp leakage, PCB contamination, temperature drift and transient behavior.',
              'decision':'1% Basic resistors acceptable as an engineering choice for artistic intensity/color CV; not a calibrated precision CV measurement. Keep calibration coefficients in firmware.',
              'rail_margin_statement':'Compare ADC fractions to0 and1 only for this ideal network. This does not replace input protection or power-off checks.'}
    (ROOT/'cv_resistor_tolerance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
