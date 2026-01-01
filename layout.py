import plotly.graph_objects as go
from plotly.subplots import make_subplots
import dash
from dash import dcc as dcc
from dash import html as html
import dash_bootstrap_components as dbc
from datetime import datetime
import dash_daq as daq
import numpy as np

def switch_card():
    onButtonStyle =dict(backgroundColor='skyblue')
    offButtonStyle=dict(backgroundColor='#32383e',borderColor='515960')
    return dbc.Card([
    dbc.CardHeader("Switches"),
    dbc.CardBody([
        dbc.Row([
            dbc.Col([
                html.Div([
                daq.PowerButton(
                id='power-button-CH',
                on=False,
                size=100,
                color='firebrick',
                label='CENTRAL HEATING',
                onButtonStyle=onButtonStyle,
                offButtonStyle=offButtonStyle,
                ),
                html.Div(id='power-button-CH-result')
                ])
            ]),
            dbc.Col([
                html.Div([
                daq.PowerButton(
                id='power-button-HW',
                on=False,
                size=100,
                color='firebrick',
                label='HOT WATER',
                onButtonStyle=onButtonStyle,
                offButtonStyle=offButtonStyle,
                ),
                html.Div(id='power-button-HW-result')
                ])
            ])
        ])
    ])])

def current_mes():
    return dbc.Card([
    dbc.CardHeader('Current monitoring'),
    dbc.CardBody([
        dbc.Row([dbc.Col(
        daq.Thermometer(
                          id='thermo',
                          min=0,
                          max=30,
                          showCurrentValue=True,
                          units="C"
        )),
        dbc.Col(
        daq.GraduatedBar(
            id='hydro',
            color={'gradient':True,"ranges":{"green":[0,55],"yellow":[55,65],"red":[65,100]}},
            showCurrentValue=True,
            vertical = True,
            step=5,
            max= 100,
            min=0,
            #size=200,
        )),
        dbc.Col(
        daq.LEDDisplay(
            id='PID_display',
            label="PID",
            color="#FF5E5E"
            )),
        ])
    ])
    ])

def temp_knob():
    return dbc.Card([
    dbc.CardHeader('Thermostat'),
    dbc.CardBody([
        daq.Knob(
            id='Temp_knob',
            color='firebrick',
            size=150,
            value=16,
            min=12,
            max=22,
            style={'fill':'#32383e'},
            showCurrentValue=True
            )
            ],)
    ])

def tab1_layout():
    return dbc.Card([  
    dbc.Row([
            dbc.Col([
                dbc.Row([switch_card(),
                    html.Div(id='blank')]),
                #dbc.Row(temp_knob())
                    ]),
            dbc.Col([current_mes()]),]),
    ]),

def low_temp(m=12,M=19,h=120):
    return dbc.Card([dbc.CardHeader('Low temperature range'),
    dbc.CardBody([
        dcc.Slider(
        id='l_temp_slider',
        min=m, max=M, step=0.5, value=16,
        marks={i: '{}'.format(i) for i in range(m,M+1)},
        tooltip={
        "always_visible": True,
        'placement':'bottom',
        "style": {"color": "LightSteelBlue", "fontSize": "20px"},
        })])
    ], style={'height':f'{h}px'})

def high_temp(m=16,M=22,h=120):
    return dbc.Card([dbc.CardHeader('High temperature range'),
    dbc.CardBody([
        dcc.Slider(id='h_temp_slider',
        min=16, max=22, step=0.5, value=19,
        marks={i: '{}'.format(i) for i in range(m,M+1)},
        tooltip={
        "always_visible": True,
        'placement':'bottom',
        "style": {"color": "LightSteelBlue", "fontSize": "20px", },
        },)
    ])
    ], style={'height':f'{h}px'})

def hours(h=120):
    return dbc.Card([dbc.CardHeader('High temperature timer'),
    dbc.CardBody([
         dcc.RangeSlider(id='timer',
    min=0, max=24, step=0.25, value=[6.5,20.5],
    marks={i: '{:02d}:00'.format(i) for i in range(0,25)},
    tooltip={"placement": "bottom", 
    "always_visible": True, 
    #"template":"{int(value):02d}:{int(value%1*60):02d}",
    "style": {"color": "LightSteelBlue", "fontSize": "20px"}}
    )])
    ], style={'height':f'{h}px'})

def tab3_layout():
    return dbc.Card([
    dbc.Row([low_temp()]),
    dbc.Row([high_temp()]),
    dbc.Row([hours()])
    ])


def mk_monit_fig(variables):
    trace1= go.Scatter(x=variables['date'][::-1], y=variables['temp'][::-1],
                name="Temperature corridor",
                line=dict(color='firebrick', width=2),
                yaxis='y')
    trace2= go.Scatter(x=variables['date'][::-1], y=variables['rh'][::-1],
                name="humidity corridor",line=dict(color='skyblue', width=2),
                yaxis='y2')
    fig_p = make_subplots(specs=[[{"secondary_y": True}]])
    fig_p.add_trace(trace1)
    fig_p.add_trace(trace2)
    if len(variables["on_CH"])>0:
        i=0    
        while i <len(variables["on_CH"]):            
            fig_p.add_vrect(x0=variables["on_CH"][i],
                x1=variables["off_CH"][i], 
                fillcolor="orange",line=dict(width=0), opacity=0.2)
            #print(i, variables["on_CH"], variables["off_CH"])
            i+=1
    fig_p.update_yaxes(title='Temperature', color='firebrick',
                    showgrid=False, secondary_y=False)
    fig_p.update_yaxes(title='Humidity', color='skyblue',
                    showgrid=False, secondary_y=True)
    fig_p.update_xaxes(range=[variables['date'].min(), variables['date'].max()])
    return fig_p

def tab2_layout(variables, sampling):
    return dbc.Card([
        dbc.CardHeader("Sensors"),
        dbc.CardBody([
                dbc.Row(dcc.Graph(
                    id="Temp-Rh",
                    figure=mk_monit_fig(variables)
                    )),
                dcc.Interval(
                    id="temperature-update",
                    interval=int(sampling*1000*60),
                    n_intervals=0,
                    ),
            ]),
        ])
def mk_boiler_fig(variables):
    trace3= go.Scatter(x=variables['date'][::-1], y=variables['on'][::-1],
                name="boiler activity",
                line=dict(color='orange', width=2,shape='hvh'),
                yaxis='y')
    totaluse=variables["conso"]*variables['on'][::-1].cumsum()
    trace4= go.Scatter(x=variables['date'][::-1], y=totaluse,
                name="total consumption",line=dict(color='white', width=2),
                yaxis='y2')
    fig_b = make_subplots(specs=[[{"secondary_y": True}]])
    fig_b.add_trace(trace3)
    fig_b.add_trace(trace4)
    fig_b.update_yaxes(title='Activity', color='orange',
                    showgrid=False, secondary_y=False)
    fig_b.update_yaxes(title='Consumption (l)', color='white',
                    showgrid=False, secondary_y=True)
    fig_b.update_xaxes(range=[variables['date'].min(), variables['date'].max()])
    return fig_b

def tab4_layout(variables):
    return dbc.Card([
    dbc.CardHeader('Boiler'),
    dbc.CardBody([
        dbc.Row(dcc.Graph(
            id='boiler',
            figure=mk_boiler_fig(variables)
            )
        )])
    ])
