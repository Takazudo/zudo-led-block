"""A5 reference design data. Values are fitted; test pads and holes are not BOM parts."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

PARTS = {
 'MCU': ('STM32G031G8U6TR','C5270180','QFN28'),
 'BUCK': ('AP63205WU-7','C2071056','TSOT26'),
 'LDO': ('TLV75533PDBVR','C404027','DBV5'),
 'LIMIT': ('TPS2552DBVR-1','C140331','DBV6'),
 'NPN': ('MMBT3904(RANGE:100-300)','C20526','SOT23'),
 'XLAT': ('SN74LVC2T45DCUR','C15741','DCU8'),
 'OPA': ('OPA197IDBVR','C221351','DBV5'),
 'ADC_BUF': ('TLV9001IDBVR','C398363','DBV5'),
 'RECT': ('PMEG4010CEJ,115','C50704','SOD323F'),
 'CLAMP': ('BAS70-04-7-F','C134375','SOT23'),
 'L': ('SPM4020T-4R7M-LR','C694586','SPM4020_LR'),
 'JACK': ('PJ-3582-B','C500090','PJ3582_ROT90'),
 'SW': ('1MS3T1B1M2QES-5','C908270','DAILYWELL_M2_SP'),
 'SH4': ('SM04B-SRSS-TB(LF)(SN)','C160404','JST_SH4'),
 'PWR3': ('530470310','C122442','PICO3'),
 'IDC': ('2.54-2*5P','C5665','IDC10'),
 'LED': ('WS2812B-2020-V6','C52917434','WS2812B_2020_V6'),
 '10M': ('0603WAF1005T5E','C7250','R0603'),
 '82k': ('0603WAF8202T5E','C23254','R0603'),
 '1k': ('0603WAF1001T5E','C21190','R0603'),
 '10k': ('0603WAF1002T5E','C25804','R0603'),
 '68k': ('0603WAF6802T5E','C23231','R0603'),
 '100k': ('0603WAF1003T5E','C25803','R0603'),
 '330': ('0603WAF3300T5E','C23138','R0603'),
 '4.7k': ('0603WAF4701T5E','C23162','R0603'),
 '100n': ('CC0603KRX7R9BB104','C14663','C0603'),
 '10n': ('0603B103K500NT','C57112','C0603'),
 '10u': ('CL21A106KAYNNNE','C15850','C0805'),
 '22u': ('CL31A226KAHNNNE','C12891','C1206'),
 '4.7u': ('CL10A475KO8NNNC','C19666','C0603'),
}

PIN_DEFS = {
 'MCU': [(str(i),n, 'power_in' if i in(3,4) else 'bidirectional') for i,n in enumerate(['PC14','PC15','VDD/VDDA','VSS/VSSA','PF2/NRST','PA0/ADC0','PA1','PA2','PA3','PA4','PA5','PA6/TIM3_CH1','PA7/TIM3_CH2','PB0','PB1','PA8','PC6','PA11','PA12','PA13/SWDIO','PA14/SWCLK','PA15','PB3','PB4','PB5','PB6','PB7','PB8'],1)],
 'BUCK': [('1','FB','input'),('2','EN','input'),('3','VIN','power_in'),('4','GND','power_in'),('5','SW','power_out'),('6','BST','passive')],
 'LDO': [('1','IN','power_in'),('2','GND','power_in'),('3','EN','input'),('4','NC','no_connect'),('5','OUT','power_out')],
 'LIMIT': [('1','IN','power_in'),('2','GND','power_in'),('3','~{EN}','input'),('4','~{FAULT}','open_collector'),('5','ILIM','passive'),('6','OUT','power_out')],
 'NPN': [('1','B','passive'),('2','E','passive'),('3','C','passive')],
 'XLAT': [('1','VCCA','power_in'),('2','A1','bidirectional'),('3','A2','bidirectional'),('4','GND','power_in'),('5','DIR','input'),('6','B2','bidirectional'),('7','B1','bidirectional'),('8','VCCB','power_in')],
 'OPA': [('1','OUT','output'),('2','V-','power_in'),('3','IN+','input'),('4','IN-','input'),('5','V+','power_in')],
 'ADC_BUF': [('1','OUT','output'),('2','V-','power_in'),('3','IN+','input'),('4','IN-','input'),('5','V+','power_in')],
 'RECT': [('1','K','passive'),('2','A','passive')],
 'CLAMP': [('1','A1','passive'),('2','K2','passive'),('3','K1/A2','passive')],
 'JACK': [('2','SLEEVE','passive'),('3','RING','passive'),('4','DETECT_A','passive'),('5','DETECT_B','passive'),('6','TIP','passive')],
 'SW': [('1','THROW_A','passive'),('2','COMMON','passive'),('3','THROW_B','passive')],
 'SH4': [('1','GND','passive'),('2','VLED','passive'),('3','DATA_A','passive'),('4','DATA_B','passive')],
 'PWR3': [('1','1','passive'),('2','2','passive'),('3','3','passive')],
 'IDC': [(str(i),str(i),'passive') for i in range(1,11)],
 'LED': [('1','DOUT','output'),('2','GND','power_in'),('3','DIN','input'),('4','VDD','power_in')],
 'TP': [('1','PAD','passive')],
 'PWR_FLAG': [('1','PWR','power_out')],
}

def component(ref, key, nets, group, xy, side='B', angle=0, value=None):
    mpn,code,fp=PARTS[key]
    typ=key if key in PIN_DEFS else ('C' if ref.startswith('C') else 'R' if ref.startswith('R') else 'L')
    return dict(ref=ref,key=key,type=typ,value=value or key,mpn=mpn,c_code=code,footprint=fp,nets={str(k):v for k,v in nets.items()},group=group,at=list(xy),side=side,angle=angle,fitted=True)

def make_controller():
    c=[]
    def add(ref,key,nets,group,xy,side='B',angle=0,value=None): c.append(component(ref,key,nets,group,xy,side,angle,value))
    # PCB local coordinates: left edge=worldX0.5, top=worldY48.5; F faces panel.
    add('U1','MCU',{1:None,2:None,3:'+3V3',4:'GND',5:'NRST',6:'CV_ADC',7:None,8:'MODE_A',9:'MODE_B',10:'LED_FAULT_N',11:'LED_ENABLE',12:'DATA_L_3V3',13:'DATA_R_3V3',14:None,15:None,16:None,17:None,18:None,19:None,20:'SWDIO',21:'SWCLK',22:None,23:None,24:None,25:None,26:None,27:None,28:None},'logic',(4.4,12.1),'F',value='STM32G031G8U6TR')
    add('U2','BUCK',{1:'+5V',2:'+12V_PROT',3:'+12V_PROT',4:'GND',5:'BUCK_SW',6:'BUCK_BST'},'power',(1.95,1.6),value='AP63205 fixed 5V')
    add('U3','LDO',{1:'+5V',2:'GND',3:'+5V',4:None,5:'+3V3'},'power',(4.4,27.65),value='TLV75533')
    add('U4','LIMIT',{1:'+5V',2:'GND',3:'LED_EN_N',4:'LED_FAULT_N',5:'LED_ILIM',6:'VLED'},'power',(4.4,23.15),value='TPS2552DBVR-1')
    add('U5','XLAT',{1:'+3V3',2:'DATA_L_3V3',3:'DATA_R_3V3',4:'GND',5:'+3V3',6:'DATA_R_5V',7:'DATA_L_5V',8:'VLED'},'logic',(4.4,33.2),'F',value='SN74LVC2T45')
    add('U6','OPA',{1:'CV_BUF',2:'-12V_PROT',3:'CV_SENSE',4:'CV_BUF',5:'+12V_PROT'},'analog',(4.4,41.5),'B',90,'OPA197 unity')
    add('U7','ADC_BUF',{1:'CV_DRIVE',2:'GND',3:'CV_FILTER',4:'CV_DRIVE',5:'+3V3'},'analog',(4.4,55.5),'B',90,'TLV9001 unity')
    add('Q1','NPN',{1:'LED_BASE',2:'GND',3:'LED_EN_N'},'power',(1.9,61.0),value='MMBT3904')
    add('D1','RECT',{1:'+12V_PROT',2:'+12V_RAW'},'power',(1.3,7.0),'F',90,'PMEG4010 +rail')
    add('D2','RECT',{1:'-12V_RAW',2:'-12V_PROT'},'power',(7.5,7.0),'F',90,'PMEG4010 -rail')
    add('D3','CLAMP',{1:'GND',2:'+3V3',3:'CV_FILTER'},'analog',(7.1,45.1),value='BAS70-04')
    add('L1','L',{1:'BUCK_SW',2:'+5V'},'power',(5.7,5.4),value='4.7uH SPM4020-LR')
    add('J1','JACK',{2:'GND',3:'GND',4:None,5:None,6:'CV_THRU'},'analog',(4.4,41.5),'F',0,'CV IN')
    add('J2','JACK',{2:'GND',3:'GND',4:None,5:None,6:'CV_THRU'},'analog',(4.4,55.5),'F',0,'CV THRU')
    add('SW1','SW',{1:'MODE_A',2:'GND',3:'MODE_B'},'analog',(4.4,25.5),'F',0,'ON / PROGRAM / CV')
    add('J3','SH4',{1:'GND',2:'VLED',3:'DATA_L',4:'DATA_R'},'logic',(4.4,12.0),'B',0,'DUAL LED G / 5 / L / R')
    # Official PicoBlade origin is pin1, at -1.25 from row center.
    add('J5','PWR3',{1:'+12V_RAW',2:'GND',3:'-12V_RAW'},'power',(3.15,5.5),'F',0,'POWER + / G / -')
    rs=[
      ('R1','10M','CV_THRU','CV_SENSE','analog',(1.15,38.7),90),
      ('R2','10M','CV_SENSE','GND','analog',(1.15,44.2),90),
      ('R3','82k','CV_BUF','CV_AFFINE','analog',(1.4,46.5),0),
      ('R4','82k','+3V3','CV_AFFINE','analog',(7.3,46.6),0),
      ('R5','82k','+3V3','CV_AFFINE','analog',(1.3,50.7),0),
      ('R6','82k','CV_AFFINE','GND','analog',(7.3,50.7),0),
      ('R7','1k','CV_AFFINE','CV_FILTER','analog',(1.15,52.6),90),
      ('R8','1k','+3V3','GND','analog',(7.4,59.4),0),
      ('R9','10k','+3V3','MODE_A','analog',(1.15,18.7),90),
      ('R10','10k','+3V3','MODE_B','analog',(7.65,18.7),90),
      ('R11','68k','LED_ILIM','GND','power',(7.3,23.0),90),
      ('R12','100k','LED_BASE','GND','power',(4.5,61.5),0),
      ('R13','10k','+3V3','LED_FAULT_N','power',(7.3,25.4),90),
      ('R14','330','DATA_L_5V','DATA_L','logic',(1.3,30.7),0),
      ('R15','330','DATA_R_5V','DATA_R','logic',(7.3,30.7),0),
      ('R16','100k','DATA_L_3V3','GND','logic',(1.3,35.7),90),
      ('R17','100k','DATA_R_3V3','GND','logic',(7.5,35.7),90),
      ('R18','100k','DATA_L','GND','logic',(1.3,32.5),0),
      ('R19','100k','DATA_R','GND','logic',(7.3,32.5),0),
      ('R20','4.7k','VLED','GND','power',(1.15,27.7),90),
      ('R21','10k','+3V3','NRST','logic',(7.3,14.4),0),
      ('R22','10k','LED_ENABLE','LED_BASE','power',(7.3,61.5),0),
      ('R23','100k','+5V','LED_EN_N','power',(1.15,23.0),90),
      ('R24','330','CV_DRIVE','CV_ADC','analog',(1.15,58.2),90),
      ('R25','1k','CV_ADC','GND','analog',(4.6,59.4),0),
    ]
    for r,k,n1,n2,g,xy,a in rs: add(r,k,{1:n1,2:n2},g,xy,'B',a,k+' 1%')
    caps=[
      ('C1','10u','+12V_PROT','GND','power',(2.0,1.5),'F',0),
      ('C2','22u','+5V','GND','power',(6.4,1.5),'F',0),
      ('C3','22u','+5V','GND','power',(4.4,8.2),'F',0),
      ('C4','100n','BUCK_BST','BUCK_SW','power',(1.35,4.7),'B',90),
      ('C5','4.7u','+5V','GND','power',(7.4,27.7),'B',90),
      ('C6','4.7u','+3V3','GND','power',(1.3,25.4),'B',90),
      ('C7','4.7u','+3V3','GND','logic',(1.2,12.0),'F',90),
      ('C8','100n','+3V3','GND','logic',(1.3,9.6),'F',0),
      ('C9','100n','+3V3','GND','logic',(1.3,33.2),'F',90),
      ('C10','100n','VLED','GND','logic',(7.5,33.2),'F',90),
      ('C11','100n','+12V_PROT','GND','analog',(4.4,38.5),'B',0),
      ('C12','100n','GND','-12V_PROT','analog',(4.4,44.5),'B',0),
      ('C13','10n','CV_AFFINE','GND','analog',(4.4,52.5),'B',0),
      ('C14','100n','NRST','GND','logic',(7.5,12.0),'F',90),
      ('C15','10u','+5V','GND','power',(4.4,18.8),'B',0),
      ('C16','10u','VLED','GND','power',(4.4,30.5),'B',0),
      ('C17','100n','+3V3','GND','analog',(4.4,58.5),'B',0),
    ]
    for r,k,n1,n2,g,xy,s,a in caps: add(r,k,{1:n1,2:n2},g,xy,s,a,k)
    for i,net in enumerate(['+3V3','GND','SWDIO','SWCLK','NRST'],1):
        c.append(dict(ref=f'TP{i}',key='TP',type='TP',value=net,mpn='',c_code='',footprint='TESTPAD',nets={'1':net},group='logic',at=[1.4+(i-1)*1.5,32.2],side='B',angle=0,fitted=False))
    overrides=ROOT/'design'/'controller_placement_override.json'
    if overrides.exists():
        import json
        placement=json.loads(overrides.read_text())['placements']
        for item in c:
            if item['ref'] in placement:item.update(placement[item['ref']])
    return dict(name='controller',title='Light Block A5 controller',width=8.8,height=62.9,thickness=1.6,layers=4,quantity_per_module=1,world_origin=[0.5,48.5,12.6],holes=[(4.4,16.5),(4.4,48.5)],components=c,route_status='placement_and_connectivity_only',power_flags=['+12V_RAW','-12V_RAW','+12V_PROT','-12V_PROT','GND','+5V'])

def make_leaf():
    c=[]
    for i,y in enumerate([3.75,28.75,53.75,78.75],1):
        c.append(component(f'D{i}','LED',{1:f'DATA_{i}_{i+1}' if i<4 else None,2:'GND',3:'DATA_IN' if i==1 else f'DATA_{i-1}_{i}',4:'VLED'},'leaf',(4.5,y),'F',0,'WS2812B-2020-V6'))
        c.append(component(f'C{i}','100n',{1:'VLED',2:'GND'},'leaf',(3.5,y+2.2),'F',0,'100n 50V X7R'))
    c.append(component('J1','SH4',{1:'GND',2:'VLED',3:'DATA_IN',4:'DATA_OTHER'},'leaf',(4.5,16.5),'F',0,'INPUT G / 5 / THIS / OTHER'))
    c.append(component('J2','SH4',{1:'GND',2:'VLED',3:'DATA_OTHER',4:'DATA_IN'},'leaf',(4.5,66.0),'F',0,'BRIDGE G / 5 / OTHER / THIS'))
    return dict(name='led_leaf',title='Light Block A5 identical LED leaf (fit twice)',width=9.0,height=82.5,thickness=.6,layers=2,quantity_per_module=2,world_origin=None,holes=[],front_edge_notches_mm=[[0,23.2,1,25.2],[0,57.3,1,59.3]],components=c,route_status='routed_native_verification_pending',power_flags=['GND','VLED'])

def make_adapter():
    c=[component('J1','IDC',{i:('-12V_RAW' if i<=2 else '+12V_RAW' if i>=9 else 'GND') for i in range(1,11)},'adapter',(3.13,10.32),'F',0,'EURORACK 10pin'),
       component('J2','PWR3',{1:'-12V_RAW',2:'GND',3:'+12V_RAW'},'adapter',(3.15,28.7),'F',0,'PWR CABLE - / G / +')]
    return dict(name='power_adapter',title='Light Block A5 passive power adapter',width=8.8,height=30,thickness=1.6,layers=2,quantity_per_module=1,world_origin=[.5,18,17.4],holes=[(4.4,2.5)],components=c,route_status='routed_native_verification_pending',power_flags=[])

def all_boards(): return [make_controller(),make_leaf(),make_adapter()]
