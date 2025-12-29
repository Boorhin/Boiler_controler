import dash, os, logging, random
from dash.dependencies import Input, Output, State
from dash import html as html
from dash import dcc as dcc
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
#from threading import Thread, Lock
#import paho.mqtt.client as mqtt
#import json
from time import sleep
import dash_bootstrap_components as dbc
import dash_daq as daq
from dash_bootstrap_templates import ThemeSwitchAIO, load_figure_template
from simple_pid import PID
from layout import *

template_theme1 = "slate"
template_theme2 = "sandstone"
load_figure_template([template_theme1,template_theme2])
url_theme1=dbc.themes.SLATE
url_theme2=dbc.themes.SANDSTONE
dbc_css = (
    "https://cdn.jsdelivr.net/gh/AnnMarieW/dash-bootstrap-templates@V1.0.1/dbc.min.css"
)

app = dash.Dash(__name__,
                external_stylesheets=[url_theme1],
                meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}])
app.title="CH Dashboard"
#app_color = {"graph_bg": "#082255", "graph_line": "#007ACE"}

# INIT LOGGER
logging.basicConfig(format='%(levelname)s:%(asctime)s__%(message)s', datefmt='%m/%d/%Y %I:%M:%S')
logger = logging.getLogger('CH_logger')
logger.setLevel(logging.DEBUG)

def init_PID(target_temp=16):
    logger.info(f'Initialising PID with target {target_temp}')  
    Kp, Ki, Kd = 1, 0.1, 0.05
    pid = PID(Kp, Ki, Kd, setpoint=target_temp, \
                  output_limits=(0, target_temp+.5), \
                  auto_mode=True, proportional_on_measurement=False)
    return pid   

def test_channel(scr,chan):
    logger.info(f'Testing channel {chan}')
    scr.ChannelEnable(chan)
    for i in range(4):
        print(f'Ready....{i}')
        sleep(i)
    for i in range(0,360):
        scr.VoltageRegulation(chan,i)
        print(i)
        sleep(0.5)
    scr.ChannelDisable(chan)
    logger.info("End of test")

def init_triac():
    from waveshare_2_CH_SCR_HAL import SCR
    logger.info('Initialising Triac')
    scr = SCR.SCR(data_mode = 0)
    angle=0
    scr.SetMode(1)
    scr.GridFrequency(50)
    scr.VoltageRegulation(1,angle)
    scr.VoltageRegulation(2,angle)
    scr.ChannelDisable(1)
    scr.ChannelDisable(2)
    #test_channel(scr, 1)
    return scr


def turn_all_off(scr):
    logger.info('Turning off Triac')
    for i in [1,2]:
        turn_off(i,scr)

def turn_on(channel,scr):
    logger.info(f'Turning on channel {channel}')
    scr.ChannelEnable(channel)
    scr.VoltageRegulation(channel,179)

def turn_off(channel,scr):
    logger.info(f'Turning off channel {channel}')
    scr.VoltageRegulation(channel,0)
    scr.ChannelDisable(channel)

class fksensor:
    logger.debug('Creating Fake sensor')
    def temperature():
        return random.randrange(8,25)
    def relative_humidity():
        return random.randrange(45,100)

def init_sensor():
    logger.debug('Initialising sensor')
    import board
    import adafruit_sht4x
    return adafruit_sht4x.SHT4x(board.I2C())

def init_graph(sampling=5, length=2):
    logger.debug('initialising graph')
    t=datetime.now()+timedelta(seconds=60)
    date=np.arange(t,t+timedelta(days=length), timedelta(minutes=sampling),dtype='datetime64[s]').astype(datetime)
    temp=np.ones(len(date))*np.nan
    rh  =np.ones(len(date))*np.nan
    return {"temp":temp,"rh":rh,"date":date[::-1]}

def roll_array(arr):
   arr[1:]=arr[:-1]
   return arr

def populate(sensor,variables):
    logger.debug('populating data')
    t,h=sensor.temperature,sensor.relative_humidity
    d=datetime.now()
    for arr,v in zip([variables['temp'],variables['rh'],variables['date']],[t,h,d]):
        arr=roll_array(arr)
        arr[0]=v

#INITIAL
logger.debug('Initialising variables')
sampling=0.25 #minutes
length=2 #days
sensor=init_sensor()
scr=init_triac()
variables=init_graph(sampling, length)
variables["on_CH"], variables["off_CH"]=[],[]
variables['CH_flag']=False

#global variables

onButtonStyle =dict(backgroundColor='skyblue')
offButtonStyle=dict(backgroundColor='#32383e',borderColor='515960')


app.layout = dbc.Container([
    dbc.Tabs(id='all_tabs',
                    children= [
        dbc.Tab(tab1_layout(),label='dashboard',tab_id='tab-main',),
        dbc.Tab(tab2_layout(variables, sampling),label='monitoring',tab_id='tab-monit')
        ])
], fluid=True, className='dbc')

@app.callback(
    [Output("Temp-Rh", "figure"),
    Output('power-button-CH', 'on'),
    Output('thermo','value'),
    Output('hydro','value'),
    Output('PID_display','value')],
    Input("temperature-update", "n_intervals"))
def gen_temps(interval):
    """
    generate the temperature graph
    :params interval: update the graph based on that interval
    """
    populate(sensor,variables)
    variables['P']=variables['pid'](variables['temp'][0])
    logger.debug(f'temp:{variables['temp'][0]}, P {variables['P']}')
    if variables['P']>variables['target']:
        logger.debug('turning on from thermostat')
        variables['CH_flag']=True
    if variables['P']<variables['target']:
        logger.debug('turning off from thermostat')
        variables['CH_flag']=False
    return [mk_monit_fig(variables), 
            variables['CH_flag'],
            variables['temp'][0],
            variables['rh'][0],
            round(variables['P'],2)]

@app.callback(
    Output('power-button-CH-result', 'children'),
    Output('power-button-CH-result', 'style'),
    Input('power-button-CH', 'on'),
)
def update_CH_b(on):
    if on:
        txt,style= 'ON', dict(color='firebrick',textAlign= 'center', padding='5px')
        if not variables['CH_flag']:
            logger.debug(f"pressing ON")
            #variables['CH_flag']=True
            #turn_on(1,scr)
    if not on:
        txt,style= 'OFF', dict(color='skyblue',textAlign= 'center', padding='5px')
        if variables['CH_flag']:
            #variables['CH_flag']=False
            #variables['off_CH'].append(datetime.now())
            #turn_off(1,scr)
            logger.debug(f"pressing OFF")
        
    return txt,style
    
@app.callback(
    Output('power-button-HW-result', 'children'),
    Output('power-button-HW-result', 'style'),
    Input('power-button-HW', 'on')
)
def update_HW_b(on):
    if on:
        turn_on(2,scr)
        return 'ON',dict(color='firebrick',textAlign= 'center', padding='5px')
    else:
        turn_off(2,scr)
        return 'OFF', dict(color='skyblue',textAlign= 'center', padding='5px')

@app.callback(
    Output('blank', 'children'),
    Input('Temp_knob','value'),
    )
def regulateCH(t):
    variables['pid']=init_PID(t)
    if 'P' in variables.keys():
         variables['pid'].set_auto_mode(True, last_output=variables['P'])
    variables['target']=t
    return None
    
if __name__ == '__main__':
    try:
        app.run(host='localhost',port=8888,debug=True)
    except KeyboardInterrupt:
        print('shutting down')
        turn_all_off(scr)
        sleep(1)
        print('Bye!')
