"""Bounded optical-fixture support insert proposal; never a fixture acceptance receipt.

The actual native record must be supplied and independently verified by the caller.
This geometry is a candidate until CAD, contact/stiffness convergence, cable access,
and manufacturing review pass. No existing fixture approval is transferred.
"""
from __future__ import annotations
import math
import a7_fixture_relief as relief

POSTS=((14.1,21.7),(10.8,25.6))
POST_DIAMETER=1.5
CONTACTS=((14.1,21.4),(15.0,26.5))
BASE=(6.5,18.0,16.2,30.0)
FIXINGS=((8.0,19.5),(8.0,24.0))
BASE_Z=(-11.0,-8.0)
POST_Z=(-8.0,0.0)
PRESSURE_Z=(8.0,14.0)
SHIM_HEIGHT=2.0
SHIM_TOLERANCE=.05


def proposal(geometry,probes):
    old=relief.design(geometry,probes)
    boxes=[(r['ref'],r['board_box_mm']) for r in old['reliefs']]
    post_checks=[]
    for i,q in enumerate(POSTS):
        # Relief boxes already include .2mm SMD/.3mm PTH clearances.
        component_gap,nearest=min((relief._box_point_dist(b,q)-POST_DIAMETER/2,ref) for ref,b in boxes)
        probe_gap,probe=min((math.dist(q,p['board_xy_mm'])-POST_DIAMETER/2-.52,p['ref']) for p in probes)
        post_checks.append({'id':f'S{i+1}','xy_mm':list(q),'diameter_mm':POST_DIAMETER,
                            'component_relief_margin_mm':round(component_gap,6),'nearest_component':nearest,
                            'probe_collar_clearance_mm':round(probe_gap,6),'nearest_probe':probe,
                            'geometry_clear':component_gap>=0 and probe_gap>=.3})
    front=[(f['ref'],f['courtyard_bbox_mm']['F']) for f in geometry['footprints']
           if f['side']=='F' and f['courtyard_bbox_mm'].get('F')]
    contact_checks=[]
    for q in CONTACTS:
        gap,near=min((relief._box_point_dist(b,q)-2.0,ref) for ref,b in front)
        contact_checks.append({'xy_mm':list(q),'body_to_courtyard_mm':round(gap,6),'nearest':near,
                               'clear':gap>=.3})
    force=2*17.44  # full maximum clamp load on one post, conservative
    area=math.pi*(POST_DIAMETER/2)**2
    inertia=math.pi*POST_DIAMETER**4/64
    e=18000.0
    length=POST_Z[1]-POST_Z[0]
    compression=force*length/(e*area)
    buckling=math.pi**2*e*inertia/(2*length)**2  # fixed-free; conservative effective length
    return {'status':'EXPERIMENTAL_NOT_ACCEPTED','old_strip_criteria':old['criterion_3_checks'],
            'post_checks':post_checks,'contact_checks':contact_checks,
            'base_box_mm':list(BASE),'base_z_mm':list(BASE_Z),'post_z_mm':list(POST_Z),
            'fixings_xy_mm':[list(q) for q in FIXINGS],
            'attachment':'two M2x8 screws from base top into new tapped probe-plate holes; 3mm base, '
                         '5mm nominal engagement in existing 6mm plate; locating/retention only, '
                         'compressive post loads seat the base directly on the probe plate',
            'fixing_source_status':'dimensional purchasing requirement, exact screw manufacturer/source not selected; '
                                   'head diameter <=3.8mm and height <=1.6mm required',
            'post_model':{'load_per_post_N':force,'assumed_E_MPa':e,'length_mm':length,
                          'axial_compression_mm':compression,'compressive_stress_MPa':force/area,
                          'fixed_free_euler_load_N':buckling,'buckling_margin':buckling/force,
                          'assumed_minimum_compressive_strength_MPa':50.0,
                          'strength_requirement_not_sourced':True},
            'pressure_plate_z_mm':list(PRESSURE_Z),'stop_shim_height_mm':SHIM_HEIGHT,
            'stop_shim_tolerance_mm':SHIM_TOLERANCE,
            'connector_clearance_mm':PRESSURE_Z[0]-.9-relief.SOURCES['PicoBlade 530470310']['mated_height_above_f_face_mm'],
            'cable_access':'existing cable leaves under raised plate; finished cable insulation/bend envelope '
                           'is unresolved and must be checked before removing J5 notch from accepted CAD',
            'manufacturing':'3mm FR-4 base with integral 8mm high Ø1.5mm posts, cutter-foot fillets below z=-6.7mm; '
                            'post tip surfaces coplanar with carrier within +/-0.02mm, assumed acceptance requirement; '
                            'machining capability/strength/abrasion not confirmed. Probe openings drilled after milling.',
            'blockers':['native current-board binding','mounted CAD/interference and cutter access',
                        'finished cable envelope','post material allowable strength and machining capability',
                        'post/land coplanarity and exposed-copper height tolerance',
                        'all spring-force corners and mesh/support geometry convergence','independent final review']}


def edge_contact(radius=.75, edge_offset=.65):
    """Area and centroid of a circular flat pin truncated by a straight board edge.

    Offset is edge X minus pin-centre X. The retained contact is x<=offset.
    Uniform pressure is an explicit model assumption; actual edge contact is unmeasured.
    """
    if edge_offset>=radius:
        return {'area_mm2':math.pi*radius**2,'area_fraction':1.0,'centroid_shift_x_mm':0.0}
    if edge_offset<=-radius:
        return {'area_mm2':0.0,'area_fraction':0.0,'centroid_shift_x_mm':None}
    chord=math.sqrt(radius**2-edge_offset**2)
    cap=radius**2*math.acos(edge_offset/radius)-edge_offset*chord
    area=math.pi*radius**2-cap
    return {'area_mm2':area,'area_fraction':area/(math.pi*radius**2),
            'centroid_shift_x_mm':-(2/3)*chord**3/area}


# Second clamp pin, stepped tip: the catalogue Ø1.5 POM thrust pin keeps only 0.025 mm of worst-case board-edge
# margin at the adopted site, so its board-contact end is turned down. The Ø1.5 shank stays the catalogue part and
# stands tip_length above the F face; only the tip touches the board. A modified purchased part is a fabrication and
# incoming-gauge REQUIREMENT, not a sourced or selected item.
STEPPED_TIP={'clamp_index':1,'contact_diameter_max_mm':1.2,'tip_length_mm':0.5,
             'status':'PROPOSED modification of the K0318.04 POM thrust pin (turned tip); not sourced, not selected, '
                      'awaiting owner approval and fabrication review',
             'gauge_requirement':'swept tip envelope at board-contact height <=1.2 mm diameter including play, runout '
                                 'and tilt; tip face flat and square; tip length 0.5 mm so the 1.5 mm shank never '
                                 'touches the board'}
# No POM grade is printed on the KIPP leaf and no datasheet is held for the pin material, so the allowable is a class
# value, not a source: compressive stress of unfilled POM at about 1 % nominal strain. It must be replaced by a
# sourced value (or a measured indentation check) before the tip is accepted.
POM_CONTACT_ALLOWABLE={'value_MPa':20.0,'class':'ASSUMED',
                       'basis':'typical unfilled POM compressive stress at about 1 % nominal strain; class value from '
                               'general engineering-plastics practice, NOT sourced; pin grade unknown',
                       'modulus_MPa':2800.0,'modulus_class':'ASSUMED'}
CONTACTS_DIAGONAL=((1.2,20.8),(15.325,26.375))


def stepped_tip_contacts(pin_diameter):
    """Board-contact diameter of each clamp pin of the adopted candidate (catalogue pin, stepped tip on one)."""
    return [STEPPED_TIP['contact_diameter_max_mm'] if i==STEPPED_TIP['clamp_index'] else pin_diameter
            for i in range(len(CONTACTS_DIAGONAL))]


def contact_stress(diameter,force_max):
    """Mean bearing pressure of a flat pin end against the ASSUMED POM allowable, and the tip's elastic shortening."""
    area=math.pi*(diameter/2)**2
    pressure=force_max/area
    return {'contact_diameter_mm':diameter,'contact_area_mm2':round(area,6),'force_max_N':force_max,
            'mean_contact_pressure_MPa':round(pressure,6),'allowable_MPa':POM_CONTACT_ALLOWABLE['value_MPa'],
            'allowable_class':POM_CONTACT_ALLOWABLE['class'],
            'utilisation':round(pressure/POM_CONTACT_ALLOWABLE['value_MPa'],6),
            'within_assumed_allowable':pressure<=POM_CONTACT_ALLOWABLE['value_MPa'],
            'tip_elastic_shortening_mm':round(pressure*STEPPED_TIP['tip_length_mm']/POM_CONTACT_ALLOWABLE['modulus_MPa'],6),
            'model':'uniform pressure on a flat end; edge stress concentration, creep, abrasion and the solder-mask '
                    'surface are not modelled and remain physical checks'}


def diagonal_proposal(geometry):
    """Full-pin candidate; geometric requirements do not certify manufactured parts."""
    contacts=CONTACTS_DIAGONAL
    notch=(4.695,23.2,12.20,29.5)
    front=[(f['ref'],f['courtyard_bbox_mm']['F']) for f in geometry['footprints']
           if f['side']=='F' and f['courtyard_bbox_mm'].get('F')]
    j5=next(b for ref,b in front if ref=='J5')
    local_gap=.30  # revised local opening requirement, not a changed component courtyard
    expanded=relief._expand(j5,local_gap)
    corners=((expanded[0],expanded[1]),(expanded[2],expanded[1]),
             (expanded[0],j5[3]),(expanded[2],j5[3]))
    notch_clear=all(relief._in_rounded(notch,[True,True,False,False],1.1,*q) for q in corners)
    checks=[]
    for q in contacts:
        gap,near=min((relief._box_point_dist(b,q)-2,ref) for ref,b in front)
        web=relief._box_point_dist(notch,q)-2.025  # accepted finished thread-cut envelope <=4.05mm
        edge=min(q[0],16.2-q[0])-.75
        checks.append({'centre_mm':list(q),'body_courtyard_gap_mm':gap,'nearest':near,
                       'thread_web_to_notch_mm':web,'thread_web_worst_mm':web-.10,
                       'outer_edge_thread_web_worst_mm':min(q[0]-relief.PRESSURE_PLATE[0],relief.PRESSURE_PLATE[2]-q[0],q[1]-relief.PRESSURE_PLATE[1],relief.PRESSURE_PLATE[3]-q[1])-2.025-.10,
                       'pin_edge_margin_mm':edge,'pin_edge_margin_worst_mm':edge-.10-(.20 if q[0]<8.1 else 0.0)})
    return {'status':'EXPERIMENTAL_NOT_ACCEPTED','support_insert':'NOT_REQUIRED_BY_THIS_CANDIDATE',
            'pressure_plate_z_mm':[6,12],'existing_standoffs_retained':True,
            'notch_mm':list(notch),'notch_radius_mm':1.1,'j5_expanded_clearance_contained':notch_clear,
            'local_notch_clearance_requirement_mm':local_gap,
            'local_notch_clearance_worst_mm':notch[2]-j5[2]-.10,
            'local_clearance_change_basis':'replace former uniform 0.50mm opening allowance with a local 0.30mm '
                                          'minimum plus explicit tolerance budget; same native component courtyard, '
                                          'same open cable exit; no PCB courtyard or DRC changes',
            'clamps':checks,'pin_maximum_accepted_swept_diameter_mm':1.5,
            'finished_thread_cut_envelope_max_mm':4.05,
            'opposite_edge_board_profile_allowance_mm':.20,
            'relative_pin_edge_tolerance_mm':.10,
            'tolerance_budget_mm':{'notch_edge':.05,'tap_position':.05,'assembled_pin_axis_including_play_runout_tilt':.05,'board_registration':.05},
            'tolerance_status':'fabrication and incoming-acceptance REQUIREMENTS, not manufacturer guarantees or measurements. '
                               'The KIPP D1=1.5mm is nominal without tolerance; every assembled pin swept envelope and axis at board-contact height must pass gauges including play/runout/tilt; tap position alone is insufficient.',
            'sleeve_overhang':'allowed above F face: sleeve end >=0.2mm above board; entire POM pin envelope remains on board',
            'contact_patch':'not inferred from pin diameter; actual tip profile/contact stress/abrasion remain physical checks',
            'remaining':['fabrication/datum tolerance evidence','pressure-plate load path/deflection around revised notch',
                         'native CAD interference','force-corner and mesh convergence','independent acceptance review']}
