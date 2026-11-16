"""Small independent electrical-network and stale-board negative controls."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from a7_return_review import Graph, RHO, verify_board_route


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


if __name__=='__main__':
    unittest.main()
