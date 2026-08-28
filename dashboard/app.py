"""
app.py — DST Airlines Dashboard v4 — FINAL
"""
import pickle
import requests
import pandas as pd
import numpy as np
import dash
from dash import dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from data import (
    API_BASE_URL,
    AIRLINES,
    AIRPORTS,
    GULF_AIRLINES,
    GULF_COUNTRIES,
    api_healthy,
    get_flights_df,
    get_gulf_flights_df,
)
from charts import ChartFactory
from weather import get_weather

BG="#0a0e1a"; CARD="#0f1523"; SURFACE="#161d2e"; BORDER="#1e2a3a"
CYAN="#00d4ff"; BLUE="#4a9eff"; PURPLE="#8b5cf6"; GREEN="#10b981"
AMBER="#f59e0b"; RED="#ef4444"; TEXT="#f1f5f9"; MUTED="#64748b"
SIDEBAR_W="220px"
DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
AIRLINE_NAMES={
    "9E":"9E — Endeavor Air","AA":"AA — American Airlines","AS":"AS — Alaska Airlines",
    "B6":"B6 — JetBlue","C5":"C5 — CommutAir","DL":"DL — Delta Air Lines",
    "F9":"F9 — Frontier","G4":"G4 — Allegiant","G7":"G7 — GoJet",
    "HA":"HA — Hawaiian","MQ":"MQ — Envoy Air","NK":"NK — Spirit",
    "OH":"OH — PSA Airlines","OO":"OO — SkyWest","PT":"PT — Piedmont",
    "QX":"QX — Horizon Air","UA":"UA — United Airlines","WN":"WN — Southwest",
    "YV":"YV — Mesa Airlines","YX":"YX — Republic Airways","ZW":"ZW — Air Wisconsin",
}
CARD_STYLE={"backgroundColor":CARD,"border":f"1px solid {BORDER}","borderRadius":"12px","padding":"20px"}
DD_STYLE={"backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}","borderRadius":"8px","fontSize":"13px"}

_MODELS=None
def get_models():
    global _MODELS
    if _MODELS is None:
        try:
            with open("/app/models.pkl","rb") as f: _MODELS=pickle.load(f)
        except: _MODELS={}
    return _MODELS

def _airport_opts(df,col):
    vals=sorted(df[col].dropna().unique()) if col in df.columns else list(AIRPORTS.keys())
    return [{"label":v,"value":v} for v in vals]

def _airline_opts(df):
    vals=sorted(df["Operating_Airline"].dropna().unique()) if "Operating_Airline" in df.columns else list(AIRLINE_NAMES.keys())
    return [{"label":AIRLINE_NAMES.get(v,v),"value":v} for v in vals]

class LB:
    @staticmethod
    def navbar():
        return html.Div([html.Div([
            html.Div([html.Span("✈",style={"fontSize":"20px","color":CYAN,"marginRight":"12px"}),
                      html.Span("DST Airlines",style={"fontSize":"17px","fontWeight":"700","color":TEXT}),
                      html.Span(" · Gulf Flight Operations",style={"fontSize":"12px","color":MUTED,"marginLeft":"8px"})],
                     style={"display":"flex","alignItems":"center"}),
            html.Div([html.Div(id="api-badge"),
                      html.Div("DATA ENGINEERING",style={"fontSize":"10px","fontWeight":"700","color":PURPLE,"border":f"1px solid {PURPLE}","borderRadius":"20px","padding":"3px 10px","marginLeft":"10px"})],
                     style={"display":"flex","alignItems":"center"}),
        ],style={"display":"flex","justifyContent":"space-between","alignItems":"center","padding":"0 24px","height":"56px"})],
        style={"backgroundColor":CARD,"borderBottom":f"1px solid {BORDER}","position":"sticky","top":"0","zIndex":"1000"})

    @staticmethod
    def sidebar():
        nav=[("▣","Overview","overview"),("✈","Airlines","airlines"),("⬡","Routes","routes"),
             ("▲","Trends","trends"),("◈","Risk Analyzer","risk"),
             ("🗺","Airport Map","map"),
             ("🕸","Route Graph","graph")]
        links=[html.Div(id=f"nav-{pid}",children=[
            html.Span(icon,style={"width":"20px","display":"inline-block","textAlign":"center","fontSize":"14px","marginRight":"10px","color":CYAN}),
            html.Span(label,style={"fontSize":"13px","whiteSpace":"nowrap","fontWeight":"500"})],
            style={"display":"flex","alignItems":"center","padding":"9px 14px","borderRadius":"8px","cursor":"pointer","color":MUTED,"marginBottom":"2px"},
            className="nav-item") for icon,label,pid in nav]
        airline_opts=[{"label":"All Airlines","value":"ALL"}]+[{"label":a,"value":a} for a in GULF_AIRLINES]
        return html.Div([
            html.Div("NAVIGATION",style={"fontSize":"9px","fontWeight":"700","color":MUTED,"letterSpacing":"2px","padding":"20px 14px 8px"}),
            *links,
            html.Div(style={"height":"1px","backgroundColor":BORDER,"margin":"14px"}),
            html.Div("FILTERS",style={"fontSize":"9px","fontWeight":"700","color":MUTED,"letterSpacing":"2px","padding":"0 14px 10px"}),
            html.Div([html.Div("Airline",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                      dcc.Dropdown(id="filter-airline",options=airline_opts,value="ALL",clearable=False,style=DD_STYLE,className="dst-dropdown")],
                     style={"padding":"0 10px","marginBottom":"14px"}),
            html.Div([html.Div("Month Range",style={"color":MUTED,"fontSize":"11px","marginBottom":"8px"}),
                      dcc.RangeSlider(id="filter-month",min=1,max=12,step=1,value=[1,12],
                                      marks={1:"Jan",3:"Mar",6:"Jun",9:"Sep",12:"Dec"})],
                     style={"padding":"0 10px","marginBottom":"14px"}),
            html.Div([html.Div("Show Only Delayed",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                      dcc.RadioItems(id="filter-delayed",
                                     options=[{"label":"  All Flights","value":"all"},{"label":"  Delayed Only","value":"delayed"}],
                                     value="all",style={"color":MUTED,"fontSize":"12px"},
                                     labelStyle={"display":"block","marginBottom":"4px"})],
                     style={"padding":"0 10px"}),
            html.Div(style={"height":"1px","backgroundColor":BORDER,"margin":"18px 14px 14px"}),
            html.Div("GULF MARKET LENS",style={"fontSize":"9px","fontWeight":"700","color":CYAN,"letterSpacing":"2px","padding":"0 14px 6px"}),
            html.Div("Country → gateway context",style={"fontSize":"10px","color":MUTED,"padding":"0 14px 10px","lineHeight":"1.4"}),
            html.Div([html.Div("Focus Country",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                      dcc.Dropdown(id="filter-gulf-country",
                                   options=[
                                       {"label":f"{v['flag']}  {country}","value":country}
                                       for country,v in GULF_COUNTRIES.items()
                                   ],value="Saudi Arabia",clearable=False,style=DD_STYLE,className="dst-dropdown")],
                     style={"padding":"0 10px","marginBottom":"14px"}),
            html.Div([html.Div("Gateway Airport",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                      dcc.Dropdown(id="filter-gulf-airport",value="RUH",clearable=False,style=DD_STYLE,className="dst-dropdown")],
                     style={"padding":"0 10px","marginBottom":"8px"}),
            html.Div("Synthetic portfolio operations · Saudi Arabia & UAE",style={"fontSize":"10px","color":MUTED,"padding":"0 10px","lineHeight":"1.4"}),
        ],style={"width":SIDEBAR_W,"minWidth":SIDEBAR_W,"backgroundColor":CARD,"borderRight":f"1px solid {BORDER}",
                 "height":"calc(100vh - 56px)","position":"sticky","top":"56px","overflowY":"auto"})

    @staticmethod
    def kpi(label,value,sub,color,icon):
        return html.Div([
            html.Div([html.Span(icon,style={"fontSize":"18px","color":color}),
                      html.Div(sub,style={"fontSize":"10px","color":MUTED,"marginLeft":"auto"})],
                     style={"display":"flex","alignItems":"center","marginBottom":"10px"}),
            html.Div(value,style={"fontSize":"26px","fontWeight":"700","color":color,"lineHeight":"1"}),
            html.Div(label,style={"fontSize":"12px","color":MUTED,"marginTop":"5px"}),
        ],style={**CARD_STYLE,"flex":"1","minWidth":"130px","borderTop":f"2px solid {color}"})

    @staticmethod
    def footer():
        return html.Div([
            html.Span("DST Airlines · Gulf Flight Operations",style={"color":MUTED,"fontSize":"11px"}),
            html.Span(" · ",style={"color":BORDER}),
            html.Span("Data Engineering · DataScientest · Feb 2026",style={"color":MUTED,"fontSize":"11px"}),
            html.Span(" · ",style={"color":BORDER}),
            html.Span("PostgreSQL · MongoDB · Neo4j · FastAPI",style={"color":MUTED,"fontSize":"11px"}),
        ],style={"backgroundColor":CARD,"borderTop":f"1px solid {BORDER}","textAlign":"center","padding":"12px 24px"})

    def page_overview(self):
        g={"displayModeBar":False}
        return html.Div([
            html.Div(id="kpi-row",style={"display":"flex","gap":"12px","flexWrap":"wrap","marginBottom":"16px"}),
            html.Div([
                html.Div([dcc.Graph(id="chart-monthly",config=g,style={"height":"300px"})],style={**CARD_STYLE,"flex":"3"}),
                html.Div([dcc.Graph(id="chart-dow",config=g,style={"height":"300px"})],style={**CARD_STYLE,"flex":"2"}),
            ],style={"display":"flex","gap":"12px","marginBottom":"12px"}),
            html.Div([
                html.Div([dcc.Graph(id="chart-histogram",config=g,style={"height":"280px"})],style={**CARD_STYLE,"flex":"1"}),
                html.Div([dcc.Graph(id="chart-top-routes",config=g,style={"height":"280px"})],style={**CARD_STYLE,"flex":"1"}),
            ],style={"display":"flex","gap":"12px"}),
        ])

    def page_airlines(self):
        g={"displayModeBar":False}
        return html.Div([
            html.Div([dcc.Graph(id="chart-airline-bar",config=g,style={"height":"340px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([dcc.Graph(id="chart-cause-stack",config=g,style={"height":"320px"})],style=CARD_STYLE),
        ])

    def page_routes(self):
        g={"displayModeBar":False}
        return html.Div([
            html.Div([dcc.Graph(id="chart-heatmap",config=g,style={"height":"480px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([dcc.Graph(id="chart-bubble",config=g,style={"height":"420px"})],style=CARD_STYLE),
        ])

    def page_trends(self):
        g={"displayModeBar":False}
        return html.Div([
            html.Div([dcc.Graph(id="chart-monthly-2",config=g,style={"height":"360px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([dcc.Graph(id="chart-top-routes-2",config=g,style={"height":"320px"})],style=CARD_STYLE),
        ])

    def page_graph(self):
        g={"displayModeBar":False}
        return html.Div([
            html.Div([
                html.Div("🕸 Airport Route Graph",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginBottom":"4px"}),
                html.Div("Explore Saudi Arabia and UAE gateway connectivity",
                         style={"fontSize":"12px","color":MUTED,"marginBottom":"16px"}),
                html.Div([
                    html.Div([
                        html.Div("From Airport",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                        dcc.Input(id="graph-from",type="text",placeholder="e.g. RUH",
                                  style={"backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}",
                                         "borderRadius":"8px","padding":"8px 12px","fontSize":"13px","width":"100%"}),
                    ],style={"flex":"1"}),
                    html.Div([
                        html.Div("To Airport",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                        dcc.Input(id="graph-to",type="text",placeholder="e.g. DXB",
                                  style={"backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}",
                                         "borderRadius":"8px","padding":"8px 12px","fontSize":"13px","width":"100%"}),
                    ],style={"flex":"1"}),
                    html.Button("Find Path 🕸",id="btn-graph",n_clicks=0,style={
                        "backgroundColor":PURPLE,"color":TEXT,"border":"none","borderRadius":"8px",
                        "padding":"10px 20px","fontSize":"13px","fontWeight":"700","cursor":"pointer","alignSelf":"flex-end"}),
                ],style={"display":"flex","gap":"16px","alignItems":"flex-end","marginBottom":"16px"}),
                html.Div(id="graph-result"),
            ],style=CARD_STYLE),
        ])
    def page_map(self):
        g={"displayModeBar":False}
        return html.Div([
            html.Div([dcc.Graph(id="chart-airport-map",config=g,style={"height":"500px"})],style=CARD_STYLE),
        ])

    def page_risk(self,df):
        ao=_airline_opts(df); oo=_airport_opts(df,"Origin"); do=_airport_opts(df,"Dest")
        dopt=[{"label":d,"value":d} for d in DAYS]
        dd=lambda lbl,fid,opts,val: html.Div([
            html.Div(lbl,style={"color":MUTED,"fontSize":"11px","marginBottom":"5px","fontWeight":"600"}),
            dcc.Dropdown(id=fid,options=opts,value=val,clearable=False,style=DD_STYLE,className="dst-dropdown"),
        ],style={"marginBottom":"14px"})
        return html.Div([
            html.Div([
                html.Div("⚡  Flight Risk Analyzer",style={"fontSize":"16px","fontWeight":"700","color":TEXT,"marginBottom":"4px"}),
                html.Div("Select a Saudi or UAE flight — live weather fetched automatically from Open-Meteo API",
                         style={"fontSize":"12px","color":MUTED,"marginBottom":"20px"}),
                html.Div([
                    html.Div([dd("Origin Airport","risk-origin",oo,oo[0]["value"] if oo else "ATL"),
                              dd("Destination Airport","risk-dest",do,do[1]["value"] if len(do)>1 else "LAX")],style={"flex":"1"}),
                    html.Div([dd("Airline","risk-airline",ao,ao[0]["value"] if ao else "UA"),
                              dd("Day of Week","risk-day",dopt,"Monday")],style={"flex":"1"}),
                ],style={"display":"flex","gap":"24px","marginBottom":"16px"}),
                html.Div(id="weather-preview",style={"marginBottom":"16px"}),
                html.Button("Analyze Flight Risk ⚡",id="btn-risk",n_clicks=0,style={
                    "backgroundColor":CYAN,"color":BG,"border":"none","borderRadius":"8px",
                    "padding":"10px 28px","fontSize":"13px","fontWeight":"700","cursor":"pointer"}),
            ],style=CARD_STYLE),
            html.Div(id="risk-result",style={"marginTop":"16px"}),
        ])

    def page_predict(self):
        fld=lambda lbl,ph,fid,typ="text": html.Div([
            html.Div(lbl,style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
            dcc.Input(id=fid,type=typ,placeholder=ph,debounce=True,style={
                "width":"100%","backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}",
                "borderRadius":"8px","padding":"8px 12px","fontSize":"13px","boxSizing":"border-box"})],
            style={"marginBottom":"12px"})
        return html.Div([html.Div([
            html.Div("Delay Prediction",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginBottom":"4px"}),
            html.Div("Enter flight & weather details",style={"fontSize":"12px","color":MUTED,"marginBottom":"20px"}),
            html.Div([
                html.Div([fld("Origin (IATA)","e.g. JFK","pred-origin"),fld("Dest (IATA)","e.g. LAX","pred-dest"),
                          fld("Airline","e.g. Delta","pred-airline"),fld("Distance (mi)","e.g. 2475","pred-distance","number")],style={"flex":"1"}),
                html.Div([fld("Temp (°C)","e.g. 12","pred-temp","number"),fld("Wind (km/h)","e.g. 18","pred-wind","number"),
                          fld("Precip (mm)","e.g. 0","pred-precip","number"),fld("Cloud (oktas)","e.g. 4","pred-cloud","number")],style={"flex":"1"}),
            ],style={"display":"flex","gap":"24px"}),
            html.Button("Predict Delay →",id="btn-predict",n_clicks=0,style={
                "backgroundColor":CYAN,"color":BG,"border":"none","borderRadius":"8px",
                "padding":"10px 28px","fontSize":"13px","fontWeight":"700","cursor":"pointer","marginTop":"8px"}),
            html.Div(id="predict-result",style={"marginTop":"20px"}),
        ],style={**CARD_STYLE,"maxWidth":"780px"})])


class App:
    def __init__(self):
        self.app=dash.Dash(__name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP,
                "https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap"],
            suppress_callback_exceptions=True,title="DST Airlines · Gulf Operations")
        self.charts=ChartFactory(); self.lb=LB()
        self._layout(); self._callbacks()

    def _layout(self):
        self.app.layout=html.Div([
            self.lb.navbar(),
            html.Div([
                self.lb.sidebar(),
                html.Div([
                    dcc.Store(id="page",data="overview"),
                    dcc.Interval(id="tick",interval=30000,n_intervals=0),
                    html.Div(id="page-header",style={"fontSize":"20px","fontWeight":"700","color":TEXT,"marginBottom":"16px"}),
                    html.Div(id="gulf-focus",style={"marginBottom":"16px"}),
                    html.Div(id="page-content"),
                ],style={"flex":"1","padding":"20px 24px","overflowY":"auto","backgroundColor":BG,"minHeight":"calc(100vh - 56px)"}),
            ],style={"display":"flex"}),
            self.lb.footer(),
        ],style={"fontFamily":"'DM Sans',sans-serif","backgroundColor":BG})

    def _callbacks(self):
        app=self.app; charts=self.charts; lb=self.lb

        @app.callback(Output("api-badge","children"),Input("tick","n_intervals"))
        def badge(_):
            c=GREEN; l="● GULF DEMO DATA"
            return html.Div(l,style={"fontSize":"10px","fontWeight":"700","color":c,"border":f"1px solid {c}","borderRadius":"20px","padding":"3px 10px"})

        app.clientside_callback(
            "function(a,b,c,d,e,f,g,cur){const t=dash_clientside.callback_context.triggered;if(!t||!t.length)return cur;return t[0].prop_id.split('.')[0].replace('nav-','');}",
            Output("page","data"),
            [Input(f"nav-{p}","n_clicks") for p in ["overview","airlines","routes","trends","risk","map","graph"]],
            State("page","data"),prevent_initial_call=True)

        def _f(country,airport,airline,months,delayed):
            market = GULF_COUNTRIES.get(country, {})
            if airport not in market.get("airports", {}):
                airport = "ALL"
            if airline not in market.get("airlines", []) and airline != "ALL":
                airline = "ALL"
            df=get_gulf_flights_df(country,airport)
            if airline and airline!="ALL" and "Operating_Airline" in df.columns: df=df[df["Operating_Airline"]==airline]
            if "Month" in df.columns: df=df[df["Month"].between(months[0],months[1])]
            if delayed=="delayed" and "Delayed" in df.columns: df=df[df["Delayed"]==1]
            return df

        ins=[Input("filter-gulf-country","value"),Input("filter-gulf-airport","value"),Input("filter-airline","value"),Input("filter-month","value"),Input("filter-delayed","value")]

        @app.callback(Output("page-content","children"),Output("page-header","children"),
                      Input("page","data"),*ins)
        def render(page,country,airport,a,m,d):
            df=_f(country,airport,a,m,d)
            titles={"overview":"Overview","airlines":"Airline Performance","routes":"Route Analysis",
                    "trends":"Monthly Trends","risk":"◈ Gulf Flight Risk Analyzer","map":"🗺 Saudi & UAE Airport Map",
        "graph":"🕸 Route Graph"}
            pages={"overview":lb.page_overview,"airlines":lb.page_airlines,"routes":lb.page_routes,"trends":lb.page_trends,"map":lb.page_map,"graph":lb.page_graph,}
            content=lb.page_risk(df) if page=="risk" else pages.get(page,lb.page_overview)()
            return content,titles.get(page,"Dashboard")

        @app.callback(
            Output("filter-gulf-airport", "options"),
            Output("filter-gulf-airport", "value"),
            Input("filter-gulf-country", "value"),
        )
        def gulf_airport_options(country):
            if country not in GULF_COUNTRIES:
                return [], None
            options = [
                {"label": f"{code} — {name}", "value": code}
                for code, name in GULF_COUNTRIES[country]["airports"].items()
            ]
            return options, options[0]["value"]

        @app.callback(
            Output("filter-airline", "options"),
            Output("filter-airline", "value"),
            Input("filter-gulf-country", "value"),
        )
        def gulf_airline_options(country):
            airlines = GULF_COUNTRIES.get(country, {}).get("airlines", GULF_AIRLINES)
            return [{"label": "All Airlines", "value": "ALL"}]+[
                {"label": airline, "value": airline} for airline in airlines
            ], "ALL"

        @app.callback(
            Output("gulf-focus", "children"),
            Input("filter-gulf-country", "value"),
            Input("filter-gulf-airport", "value"),
        )
        def gulf_focus(country, airport):
            if country not in GULF_COUNTRIES:
                return html.Div([
                    html.Span("GULF MARKET LENS",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.5px","marginRight":"12px"}),
                    html.Span("Select a country and gateway to focus the network context.",style={"fontSize":"12px","color":MUTED}),
                ],style={**CARD_STYLE,"padding":"12px 16px","borderLeft":f"3px solid {CYAN}"})
            market = GULF_COUNTRIES[country]
            airport_name = market["airports"].get(airport, "All gateways")
            return html.Div([
                html.Div([
                    html.Span(f"{market['flag']}  {country}",style={"fontSize":"14px","fontWeight":"700","color":TEXT}),
                    html.Span(" · ",style={"color":MUTED}),
                    html.Span(f"{airport or 'All'} · {airport_name}",style={"fontSize":"12px","color":CYAN}),
                ]),
                html.Div(f"{market['focus']} · the KPIs and charts below are filtered to this origin gateway",style={"fontSize":"11px","color":MUTED,"marginTop":"5px"}),
            ],style={**CARD_STYLE,"padding":"12px 16px","borderLeft":f"3px solid {GREEN}"})

        @app.callback(Output("kpi-row","children"),*ins)
        def kpis(country,airport,a,m,d):
            df=_f(country,airport,a,m,d); t=len(df)
            delayed=int(df["Delayed"].sum()) if "Delayed" in df.columns else 0
            rate=round(df["Delayed"].mean()*100,1) if t and "Delayed" in df.columns else 0
            avg=round(df[df["DepDelay"]>0]["DepDelay"].mean(),1) if t else 0
            routes=df.groupby(["Origin","Dest"]).ngroups if "Origin" in df.columns else 0
            return [lb.kpi("Total Flights",f"{t:,}","FLIGHTS",TEXT,"▣"),
                    lb.kpi("Delayed Flights",f"{delayed:,}","DELAYED",AMBER,"⏱"),
                    lb.kpi("Delay Rate",f"{rate}%","RATE",AMBER,"↑"),
                    lb.kpi("Avg Delay",f"{avg} min","AVG",CYAN,"◷"),
                    lb.kpi("Airlines",str(df["Operating_Airline"].nunique() if "Operating_Airline" in df.columns else 0),"CARRIERS",GREEN,"✈"),
                    lb.kpi("Routes",str(routes),"O-D PAIRS",PURPLE,"⬡")]

        @app.callback(Output("chart-monthly","figure"),*ins)
        def cm(*args): return charts.monthly_trend(_f(*args))
        @app.callback(Output("chart-dow","figure"),*ins)
        def cd(*args): return charts.dow_delay(_f(*args))
        @app.callback(Output("chart-histogram","figure"),*ins)
        def ch(*args): return charts.delay_histogram(_f(*args))
        @app.callback(Output("chart-top-routes","figure"),*ins)
        def ct(*args): return charts.top_routes(_f(*args))
        @app.callback(Output("chart-airline-bar","figure"),*ins)
        def ca(*args): return charts.airline_delay_bar(_f(*args))
        @app.callback(Output("chart-cause-stack","figure"),*ins)
        def cc(*args): return charts.delay_cause_stack(_f(*args))
        @app.callback(Output("chart-heatmap","figure"),*ins)
        def chm(*args): return charts.route_heatmap_top(_f(*args))
        @app.callback(Output("chart-bubble","figure"),*ins)
        def cb(*args): return charts.top_routes_bubble(_f(*args))
        @app.callback(Output("chart-monthly-2","figure"),*ins)
        def cm2(*args): return charts.monthly_trend(_f(*args))
        @app.callback(Output("chart-top-routes-2","figure"),*ins)
        def ct2(*args): return charts.top_routes(_f(*args))

        @app.callback(Output("chart-airport-map","figure"),*ins)
        def c_map(*args): return charts.airport_map(_f(*args))

        @app.callback(
            Output("graph-result","children"),
            Input("btn-graph","n_clicks"),
            State("graph-from","value"),
            State("graph-to","value"),
            prevent_initial_call=True,
        )
        def find_path(n, from_iata, to_iata):
            if not from_iata or not to_iata:
                return html.Div("⚠ Enter both airports.",style={"color":AMBER})
            from_iata = from_iata.upper().strip()
            to_iata = to_iata.upper().strip()
            gulf_airports = {
                code
                for market in GULF_COUNTRIES.values()
                for code in market["airports"]
            }
            if from_iata in gulf_airports and to_iata in gulf_airports:
                if from_iata == to_iata:
                    return html.Div("⚠ Select two different Gulf airports.",style={"color":AMBER})
                stops = [from_iata, to_iata]
                return html.Div([
                    html.Div("✅ Direct Gulf network connection",style={"fontSize":"14px","fontWeight":"700","color":GREEN,"marginBottom":"12px"}),
                    html.Div([
                        html.Div([
                            html.Span(s,style={"backgroundColor":SURFACE,"border":f"1px solid {CYAN}","borderRadius":"8px",
                                               "padding":"6px 14px","fontSize":"13px","fontWeight":"700","color":CYAN}),
                            html.Span(" → ",style={"color":MUTED,"fontSize":"16px","margin":"0 4px"}) if i == 0 else None,
                        ],style={"display":"inline-flex","alignItems":"center"}) for i,s in enumerate(stops)
                    ],style={"display":"flex","flexWrap":"wrap","alignItems":"center","gap":"4px"}),
                ],style={**CARD_STYLE,"borderTop":f"2px solid {GREEN}","marginTop":"16px"})
            try:
                response = requests.get(
                    f"{API_BASE_URL}/routes/path",
                    params={"origin": from_iata, "dest": to_iata},
                    timeout=10,
                )
                if response.status_code == 404:
                    return html.Div("❌ No path found.",style={"color":RED,"fontSize":"13px"})
                response.raise_for_status()
                route = response.json()
                stops = route["airports"]
                hops = route["hops"]
                return html.Div([
                    html.Div(f"✅ Shortest path: {hops} stop(s)",style={"fontSize":"14px","fontWeight":"700","color":GREEN,"marginBottom":"12px"}),
                    html.Div([
                        html.Div([
                            html.Span(s,style={"backgroundColor":SURFACE,"border":f"1px solid {CYAN}","borderRadius":"8px",
                                               "padding":"6px 14px","fontSize":"13px","fontWeight":"700","color":CYAN}),
                            html.Span(" → ",style={"color":MUTED,"fontSize":"16px","margin":"0 4px"}) if i<len(stops)-1 else None,
                        ],style={"display":"inline-flex","alignItems":"center"}) for i,s in enumerate(stops)
                    ],style={"display":"flex","flexWrap":"wrap","alignItems":"center","gap":"4px"}),
                ],style={**CARD_STYLE,"borderTop":f"2px solid {GREEN}","marginTop":"16px"})
            except Exception as e:
                return html.Div(f"❌ Error: {str(e)}",style={"color":RED,"fontSize":"13px"})

        @app.callback(Output("weather-preview","children"),Input("risk-origin","value"),Input("risk-dest","value"))
        def weather_prev(origin,dest):
            if not origin or not dest: return None
            def wcard(iata,w):
                if not w: return html.Div([html.Div(f"🌍 {iata}",style={"fontSize":"12px","fontWeight":"700","color":TEXT}),html.Div("No data",style={"fontSize":"11px","color":MUTED})],style={**CARD_STYLE,"flex":"1"})
                return html.Div([
                    html.Div(f"🌍 {iata} — Live Weather",style={"fontSize":"12px","fontWeight":"700","color":CYAN,"marginBottom":"8px"}),
                    html.Div([html.Span(f"🌡️ {w['temp']}°C",style={"marginRight":"16px","fontSize":"12px","color":TEXT}),
                              html.Span(f"💨 {w['wind_speed']} km/h",style={"marginRight":"16px","fontSize":"12px","color":TEXT}),
                              html.Span(f"🌧️ {w['precip']} mm",style={"marginRight":"16px","fontSize":"12px","color":TEXT}),
                              html.Span(f"☁️ {w['cloud_cover']}/8",style={"fontSize":"12px","color":TEXT})]),
                ],style={**CARD_STYLE,"flex":"1","borderTop":f"2px solid {CYAN}"})
            return html.Div([wcard(origin,get_weather(origin)),wcard(dest,get_weather(dest))],style={"display":"flex","gap":"12px"})

        @app.callback(Output("risk-result","children"),Input("btn-risk","n_clicks"),
                      State("risk-origin","value"),State("risk-dest","value"),State("risk-airline","value"),State("risk-day","value"),
                      prevent_initial_call=True)
        def risk(n,origin,dest,airline,day):
            if not all([origin,dest,airline,day]): return html.Div("⚠ Fill all fields.",style={"color":AMBER,"fontSize":"13px"})
            df=get_gulf_flights_df()
            rdf=df[(df.get("Origin",pd.Series())== origin)&(df.get("Dest",pd.Series())==dest)] if "Origin" in df.columns else pd.DataFrame()
            ddf=df[df.get("DayOfWeek",pd.Series())==day] if "DayOfWeek" in df.columns else pd.DataFrame()
            adf=df[df.get("Operating_Airline",pd.Series())==airline] if "Operating_Airline" in df.columns else pd.DataFrame()
            rr=round(rdf["Delayed"].mean()*100,1) if len(rdf)>0 and "Delayed" in rdf.columns else None
            dr=round(ddf["Delayed"].mean()*100,1) if len(ddf)>0 and "Delayed" in ddf.columns else None
            ar=round(adf["Delayed"].mean()*100,1) if len(adf)>0 and "Delayed" in adf.columns else None
            ad=round(rdf["DepDelay"].mean(),1)    if len(rdf)>0 and "DepDelay" in rdf.columns else None
            available_rates = [rate for rate in [rr, dr, ar] if rate is not None]
            prob=(sum(available_rates)/len(available_rates)/100) if available_rates else 0.30
            exp=max(0,ad or 20)
            if prob<0.3:   rc=GREEN;rl="LOW RISK";   ri="✅"
            elif prob<0.6: rc=AMBER;rl="MEDIUM RISK";ri="⚠️"
            else:          rc=RED;  rl="HIGH RISK";  ri="🔴"
            return html.Div([
                html.Div([
                    html.Div([dcc.Graph(figure=charts.risk_gauge(prob),config={"displayModeBar":False},style={"height":"280px"})],style={"flex":"1"}),
                    html.Div([
                        html.Div(f"{ri}  {rl}",style={"fontSize":"28px","fontWeight":"700","color":rc,"marginBottom":"12px"}),
                        html.Div(f"{round(prob*100,1)}% delay probability",style={"fontSize":"16px","color":MUTED,"marginBottom":"20px"}),
                        html.Div(style={"width":"100%","height":"6px","backgroundColor":BORDER,"borderRadius":"3px","marginBottom":"20px","overflow":"hidden"},
                                 children=[html.Div(style={"width":f"{round(prob*100)}%","height":"100%","backgroundColor":rc,"borderRadius":"3px"})]),
                        html.Div(f"Route: {origin} → {dest}",style={"fontSize":"13px","color":TEXT,"marginBottom":"6px"}),
                        html.Div(f"Airline: {AIRLINE_NAMES.get(airline,airline)}",style={"fontSize":"13px","color":TEXT,"marginBottom":"6px"}),
                        html.Div(f"Day: {day}",style={"fontSize":"13px","color":TEXT,"marginBottom":"16px"}),
                        html.Div(f"Expected delay: ~{round(exp)} min",style={"fontSize":"13px","color":CYAN,"fontWeight":"600"}),
                    ],style={"flex":"1","padding":"20px 0"}),
                ],style={"display":"flex","gap":"24px","alignItems":"center"}),
            ],style={**CARD_STYLE,"borderTop":f"3px solid {rc}","marginBottom":"12px"})



    def run(self,debug=False,port=8050):
        self.app.run(debug=debug,host="0.0.0.0",port=port)

if __name__=="__main__":
    App().run(debug=False,port=8050)
