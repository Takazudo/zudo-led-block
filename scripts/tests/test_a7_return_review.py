"""Small independent electrical-network and stale-board negative controls."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from a7_return_review import (ACCEPTANCE, ALPHA, CORNERS, CV_PER_ADC_V, CV_SLEEVE_WEIGHT, CV_WEIGHTS, GAIN,
                              LAYERS, Graph, RHO, kelvin_audit, verify_board_route)

REPO = Path(__file__).resolve().parents[2]


class ReturnReview(unittest.TestCase):
    def example(self):
        pads = []
        for ref,x in [('J5',0),('U7',1),('J3',2)]:
            pad = '2' if ref!='J3' else '1'
            pads.append({'ref':ref,'pad':pad,'net':'/GND','polys':{'F.Cu':[
                [[x-.024,-.024],[x+.024,-.024],[x+.024,.024],[x-.024,.024]]]},'drill':None})
        proposal = {'tracks':[{'net':'/GND','layer':'F.Cu','start':[0,0],'end':[2,0],'width':.3}],'vias':[]}
        return Graph({'pads':pads},proposal),proposal

    def test_known_series_resistance_and_load(self):
        graph,_ = self.example()
        unit_r = RHO/(.3*.035)
        self.assertAlmostEqual(graph.shortest('J5.2','J3.1'),2*unit_r,places=12)
        voltage = graph.solve({'J3.1':.44})
        self.assertAlmostEqual(voltage['U7.2'],.44*unit_r,places=10)
        self.assertAlmostEqual(voltage['J3.1'],.44*2*unit_r,places=10)

    def test_shared_led_analog_return_is_rejected(self):
        graph,_ = self.example()
        audit = graph.filled_star_audit(['kicad_pcb'])
        self.assertTrue(any('mixed branch' in error for error in audit['failures']))

    def test_unrelated_native_board_cannot_validate_proposal(self):
        _,proposal = self.example()
        with self.assertRaisesRegex(ValueError,'PCB tracks do not match'):
            verify_board_route(['kicad_pcb'],proposal)

    def test_filled_zone_touching_signal_pad_edge_is_rejected(self):
        pads=[]
        for ref,pad,x,y,w,h in [('J5','2',0,0,.1,.1),('J3','1',0,3,.1,.1),('U7','2',3,0,2,2)]:
            pads.append({'ref':ref,'pad':pad,'net':'/GND','polys':{'F.Cu':[
                [[x-w/2,y-h/2],[x+w/2,y-h/2],[x+w/2,y+h/2],[x-w/2,y+h/2]]]},'drill':None})
        route={'tracks':[{'net':'/GND','layer':'F.Cu','start':[0,0],'end':end,'width':.3} for end in ([0,3],[3,0])],'vias':[]}
        graph=Graph({'pads':pads},route)
        zone=['zone',['net','/GND'],['filled_polygon',['layer','F.Cu'],['pts',
              ['xy','-.1','.8'],['xy','3.5','.8'],['xy','3.5','1.2'],['xy','-.1','1.2']]]]
        audit=graph.filled_star_audit(['kicad_pcb',zone])
        self.assertIn('U7.2',audit['filled_polygons'][0]['pad_contacts'])
        self.assertTrue(audit['failures'])

    def star(self, power_layer, signal_layer):
        """J5.2 as a plated pad on every layer; one LED return and one CV reference trace."""
        square = lambda x, y, h: [[x-h, y-h], [x+h, y-h], [x+h, y+h], [x-h, y+h]]
        pads = [{'ref': 'J5', 'pad': '2', 'net': '/GND', 'polys': {l: [square(0, 0, .4)] for l in LAYERS},
                 'drill': {'at': [0, 0], 'size': [.5, .5]}},
                {'ref': 'J3', 'pad': '1', 'net': '/GND', 'polys': {power_layer: [square(0, 5, .1)]}, 'drill': None},
                {'ref': 'U7', 'pad': '2', 'net': '/GND', 'polys': {signal_layer: [square(5, 0, .1)]}, 'drill': None}]
        route = {'tracks': [{'net': '/GND', 'layer': power_layer, 'start': [0, 0], 'end': [0, 5], 'width': .3},
                            {'net': '/GND', 'layer': signal_layer, 'start': [0, 0], 'end': [5, 0], 'width': .3}], 'vias': []}
        return {'pads': pads}, route

    def test_star_pad_faces_are_separate_nodes_joined_by_the_barrel(self):
        geometry, route = self.star('F.Cu', 'B.Cu')
        graph = Graph(geometry, route)
        self.assertNotEqual(graph.terms['J5.2@F.Cu'], graph.terms['J5.2@B.Cu'])
        audit = graph.filled_star_audit(['kicad_pcb'])
        self.assertEqual(audit['star_pad_faces'], {'F.Cu': ['power'], 'In1.Cu': [], 'In2.Cu': [], 'B.Cu': ['signal']})
        self.assertEqual(audit['failures'], [])
        # the pin bonded on either face: LED current never raises the CV reference above the pin
        for face in ('F.Cu', 'B.Cu'):
            voltage = graph.solve({'J3.1': .44}, reference='J5.2@' + face)
            self.assertAlmostEqual(voltage['U7.2'], voltage['J5.2@B.Cu'], places=12)
        self.assertGreater(graph.solve({'J3.1': .44}, reference='J5.2@B.Cu')['J5.2@F.Cu'], 0)

    def test_both_branches_on_one_pad_face_are_rejected(self):
        geometry, route = self.star('F.Cu', 'F.Cu')
        failures = Graph(geometry, route).filled_star_audit(['kicad_pcb'])['failures']
        self.assertTrue(any('J5.2 F.Cu carries' in f for f in failures))
        self.assertTrue(any('J5.2 B.Cu carries' in f for f in failures))

    def test_hot_thin_corner_scales_every_resistance(self):
        geometry, route = self.star('F.Cu', 'B.Cu')
        nominal = Graph(geometry, route).shortest('J3.1', 'J5.2@F.Cu')
        corner = CORNERS['hot_85C_thin_copper']
        self.assertAlmostEqual(Graph(geometry, route, corner=corner).shortest('J3.1', 'J5.2@F.Cu') / nominal,
                               (1 + ALPHA * 65) / (.8 * .8), places=9)

    def test_track_ending_on_a_via_annulus_is_connected(self):
        square = lambda x, y, h: [[x-h, y-h], [x+h, y-h], [x+h, y+h], [x-h, y+h]]
        pads = [{'ref': 'U1', 'pad': '4', 'net': '/GND', 'polys': {'F.Cu': [square(0, 0, .1)]}, 'drill': None},
                {'ref': 'C8', 'pad': '2', 'net': '/GND', 'polys': {'B.Cu': [square(3, 0, .1)]}, 'drill': None}]
        route = {'tracks': [{'net': '/GND', 'layer': 'F.Cu', 'start': [0, 0], 'end': [1, 0], 'width': .3},
                            {'net': '/GND', 'layer': 'B.Cu', 'start': [1.2, 0], 'end': [3, 0], 'width': .3}],
                 'vias': [{'net': '/GND', 'at': [1, 0], 'size': .5, 'drill': .2}]}
        self.assertGreater(Graph({'pads': pads}, route).shortest('U1.4', 'C8.2'), 0)
        route['tracks'][1]['start'] = [1.3, 0]     # past the annulus: no copper contact
        with self.assertRaisesRegex(ValueError, 'disconnected'):
            Graph({'pads': pads}, route).shortest('U1.4', 'C8.2')

    def test_firmware_weights_leave_only_the_uncredited_source_return(self):
        # CV = 10.64*VADC - 4*VDD; the on-board weights sum to -1 because the patched source is taken to
        # hold CV against the J5.2 pin, and crediting the CV IN sleeve completes the set to zero.
        self.assertAlmostEqual(sum(CV_WEIGHTS.values()), -1, places=12)
        self.assertAlmostEqual(sum(CV_WEIGHTS.values()) + CV_SLEEVE_WEIGHT, 0, places=12)
        self.assertAlmostEqual(CV_PER_ADC_V, 10.64, places=12)
        self.assertAlmostEqual(CV_WEIGHTS['R25.2'], 10.64 * (1 - GAIN), places=12)

    def test_reference_tap_sharing_load_copper_is_rejected(self):
        square = lambda x, y, h: [[x-h, y-h], [x+h, y-h], [x+h, y+h], [x-h, y+h]]
        at = {'U3.5': (0, 0), 'C8.1': (4, 0), 'U1.3': (5, 0), 'R4.1': (4, 3), 'R5.1': (4, 5)}
        pads = [{'ref': k.split('.')[0], 'pad': k.split('.')[1], 'net': '/+3V3', 'polys': {'F.Cu': [square(x, y, .1)]},
                 'drill': None} for k, (x, y) in at.items()]
        track = lambda a, b: {'net': '/+3V3', 'layer': 'F.Cu', 'start': list(a), 'end': list(b), 'width': .2}
        good = {'tracks': [track((0, 0), (4, 0)), track((4, 0), (5, 0)), track((4, 0), (4, 3)), track((4, 3), (4, 5))], 'vias': []}
        self.assertEqual(kelvin_audit({'pads': pads}, good)['failures'], [])
        # the taps hang on the supply run before the decoupler: the MCU load drop is in the reference
        bad = {'tracks': [track((0, 0), (2, 0)), track((2, 0), (4, 0)), track((4, 0), (5, 0)),
                          track((2, 0), (2, 3)), track((2, 3), (4, 3)), track((4, 3), (4, 5))], 'vias': []}
        self.assertTrue(kelvin_audit({'pads': pads}, bad)['failures'])


class RetainedRecord(unittest.TestCase):
    """The committed review record must belong to the committed board, route and thresholds."""

    def test_record_is_bound_to_the_current_board_and_route(self):
        record = json.loads((REPO / 'engineering/a7/verification/controller/return-review.json').read_text())
        for key, path in [('board', 'engineering/a7/electronics/controller/controller.kicad_pcb'),
                          ('routes', 'engineering/a7/verification/routing/route_proposal_seed0.json')]:
            digest = hashlib.sha256((REPO / path).read_bytes()).hexdigest()
            self.assertEqual(record['inputs'][key + '_sha256'], digest, f'stale {key} in the retained review')
        self.assertEqual(record['acceptance'], ACCEPTANCE)
        self.assertTrue(record['status']['pass'])
        for name in ('incremental_LED_DC_budget', 'combined_DC_budget'):
            self.assertEqual(record[name]['corner'], ACCEPTANCE['corner'])
            self.assertLessEqual(record[name]['bound_LSB'], record[name]['allocation_LSB'])
        self.assertEqual(record['filled_star_audit']['failures'], [])
        self.assertEqual(record['kelvin_audit']['failures'], [])
        self.assertEqual(record['coupling']['failures'], [])


if __name__=='__main__':
    unittest.main()
