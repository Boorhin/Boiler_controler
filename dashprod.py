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
logger.setLevel(logging.INFO)

def init_data_record():
    try:
        lastfile=sorted([os.path.join('logs',l) for l in os.listdir('logs')],key=os.path.getmtime)[-1]
        logger.debug(f'selecting file {lastfile})')
        with open(lastfile,'r') as l:
            logger.debug(f'file {lastfile} opened')
            for line in l:
                pass
            lasthours=line.strip().split('\t')[-1]
        logger.info(f'Adding {lasthours} hours of activity from former logs.')
    except:
        logger.error('No former log or invalid log files. No former hours added')
        lasthours=0
    timestamp='{:%Y-%m-%d_%H:%M:%S}'.format(datetime.now())
    logger.info(f'Initialising data file {timestamp}.log')
    variables=['datetime','temp','Rh','activity(h)']
    with open(f'logs{os.sep}{timestamp}.log','w') as f:
        for col in variables:
            f.write(f'{col}\t')
        f.write('\n')
    return timestamp,float(lasthours)

def write_record(variables):
    with open(f"logs{os.sep}{variables['datalog']}.log",'a') as f:
        f.write('{:%Y-%m-%d_%H:%M:%S}\t'.format(variables['date'][0]))
        f.write(f'{round(variables['temp'][0],1)}\t')
        f.write(f'{round(variables['rh'][0],1)}\t')
        f.write(f"{round(variables['run']+variables['old run'],2)}\n")

def init_PID(target_temp=16):
    logger.info(f'Initialising PID with target {target_temp}')
    Kp, Ki, Kd = 1, 0.1, 0.05
    pid = PID(Kp, Ki, Kd, setpoint=target_temp, \
                  output_limits=(0, target_temp+.25), \
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
    logger.debug(f'Turning on channel {channel}')
    scr.ChannelEnable(channel)
    scr.VoltageRegulation(channel,179)

def turn_off(channel,scr):
    logger.debug(f'Turning off channel {channel}')
    scr.VoltageRegulation(channel,0)
    scr.ChannelDisable(channel)

class fksensor:
    logger.debug('Creating Fake sensor')
    def temperature():
        return random.randrange(8,25)
    def relative_humidity():
        return random.randrange(45,100)

def init_sensor():
    logger.info('Initialising sensor')
    import board
    import adafruit_sht4x
    return adafruit_sht4x.SHT4x(board.I2C())

def init_graph(variables):
    logger.info('initialising graph')
    t=datetime.now()+timedelta(seconds=5)
    variables['date']=np.ones((int(timedelta(days=variables['length'])/timedelta(minutes=variables['sampling']))), dtype='datetime64[ms]').astype(datetime)
    variables['temp']=np.ones(len(variables['date']))*np.nan
    variables['rh']  =np.ones(len(variables['date']))*np.nan
    variables['on']=np.zeros(len(variables['date'])).astype('bool')
    return variables

def roll_array(arr,v):
    arr[:-1]=arr[1:]
    arr[-1]=v
    return arr

def populate(sensor,variables):
    logger.debug('populating data')
    t,h=sensor.temperature,sensor.relative_humidity
    d=datetime.now()
    for arr,v in zip([variables['temp'],variables['rh'],variables['date']],[t,h,d]):
        arr=roll_array(arr,v)

def pop_boiler(variables):
    logger.debug('populating boiler data')
    variables['on']=roll_array(variables['on'],variables['boiler_flag'])

def selectemp(timer,lt,ht):
    logger.debug('selecting thermostat value according to timer')
    now=datetime.now()
    h=now.hour+now.minute/60
    if timer[0]<h and h<timer[1]:
        logger.debug('High temp stat')
        return ht
    else:
        logger.debug('low temp stat')
        return lt

def reinit_PID(variables,t):
    logger.info(f"reinitialising PID with target {t}")
    variables['pid']=init_PID(t)
    if 'P' in variables.keys():
         variables['pid'].set_auto_mode(True, last_output=variables['P'])
    variables['target']=t

#INITIAL
logger.info('Initialising variables')
sensor=init_sensor()
scr=init_triac()
variables={}
variables['sampling']=.25  #minutes
variables['length']=7 #days
variables=init_graph(variables)
variables["on_CH"], variables["off_CH"]=[],[]
variables['CH_flag']=False
variables['boiler_flag']=False
variables['target']=16
variables['lt']=16
variables['ht']=19
variables['timer']=[5.75,20.5]
variables['pid']=init_PID()
#variables["conso"]=3.4 # nozzle l/h
variables["conso"] =variables['sampling']/60 #hours of use
variables['run']=0
variables['datalog'],variables['old run']=init_data_record()
variables['offset']=0
variables['window']= variables['length']*24 #graphing

onButtonStyle =dict(backgroundColor='skyblue')
offButtonStyle=dict(backgroundColor='#32383e',borderColor='515960')


app.layout = dbc.Container([
    dbc.Tabs(id='all_tabs',
                    children= [
        dbc.Tab(tab1_layout(),label='dashboard',tab_id='tab-main',),
        dbc.Tab(tab3_layout(variables),label="settings",tab_id='tab-settings'),
        dbc.Tab(tab2_layout(variables),label='monitoring',tab_id='tab-monit'),
        dbc.Tab(tab4_layout(variables),label='boiler',tab_id='tab-boiler'),
        dbc.Tab(tab5_layout(variables),label='Misc', tab_id='tab-misc'),
        ])
], fluid=True, className='dbc')

@app.callback(
    [Output("Temp-Rh", "figure"),
    Output('power-button-CH', 'on'),
    Output('thermo','value'),
    Output('hydro','value'),
    Output('PID_display','value'),
    Output('boiler','figure'),
    Output('H_display','value'),],
    [Input("temperature-update", "n_intervals"),
    Input('l_temp_slider','value'),
    Input('h_temp_slider','value'),
    Input('timer','value'),
    Input('window','value')],
    State('power-button-HW', 'on'))
def gen_temps(interval,lt,ht,timer,window,HW):
    """
    generate the temperature graph
    :params interval: update the graph based on that interval
    :params lt: Low thermostat value
    :params ht: high thermostat value
    :params timer: list of hour range when high thermostat is active
    :params HW: bool if hot water button engaged
    """
    variables['window']=window
    t=selectemp(timer,lt,ht)
    variables['lt']=lt
    variables['ht']=ht
    variables['timer']=timer
    if variables['target'] != t:
        reinit_PID(variables,t)
    populate(sensor,variables)
    variables['P']=variables['pid'](variables['temp'][-1])
    logger.debug(f'temp:{variables['temp'][-1]}, P {variables['P']}')
    variables['boiler_flag']=False
    if variables['P']>variables['target']:
        logger.debug('turning on from thermostat')
        variables['CH_flag']=True
        variables['boiler_flag']=True
    if variables['P']<variables['target']:
        logger.debug('turning off from thermostat')
        variables['CH_flag']=False
    if HW:
        variables['boiler_flag']=True
    pop_boiler(variables)
    write_record(variables)
    return [mk_monit_fig(variables), 
            variables['CH_flag'],
            variables['temp'][-1],
            variables['rh'][-1],
            round(variables['P'],2),
            mk_boiler_fig(variables),
            round(variables['run']+variables['old run'],1),]

@app.callback(
    Output('power-button-CH-result', 'children'),
    Output('power-button-CH-result', 'style'),
    Input('power-button-CH', 'on'),)
def update_CH_b(on):
    if on:
        txt,style= 'ON', dict(color='firebrick',textAlign= 'center', padding='5px')
        if not variables['CH_flag']:
            logger.debug(f"pressing ON")
        #turn_on(1,scr)
    if not on:
        txt,style= 'OFF', dict(color='skyblue',textAlign= 'center', padding='5px')
        if variables['CH_flag']:
            logger.debug(f"pressing OFF")
        #turn_off(1,scr)
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



if __name__ == '__main__':
    try:
        app.run(host='localhost',port=8888,debug=True, use_reloader=False)
    except:
        logger.warning('shutting down')
        turn_all_off(scr)
        sleep(1)
        print('Bye!')
