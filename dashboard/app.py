"""
app.py — DST Airlines Dashboard v4 — FINAL
"""
from datetime import date

import pandas as pd
import numpy as np
import dash
from dash import dcc, html, dash_table, Input, Output, State
import dash_bootstrap_components as dbc
from data import (
    API_BASE_URL,
    AIRPORTS,
    GULF_AIRLINES,
    GULF_ANALYTICS_YEARS,
    GULF_COUNTRIES,
    get_gulf_flights_df,
    get_live_flights,
)
from charts import ChartFactory
from ml_client import get_ml_status, predict_gulf_delay
from weather import get_weather

BG="#0a0e1a"; CARD="#0f1523"; SURFACE="#161d2e"; BORDER="#1e2a3a"
CYAN="#00d4ff"; BLUE="#4a9eff"; PURPLE="#8b5cf6"; GREEN="#10b981"
AMBER="#f59e0b"; RED="#ef4444"; TEXT="#f1f5f9"; MUTED="#64748b"
SIDEBAR_W="220px"
DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
AIRLINE_NAMES={name:name for name in GULF_AIRLINES}
CARD_STYLE={"backgroundColor":CARD,"border":f"1px solid {BORDER}","borderRadius":"12px","padding":"20px"}
DD_STYLE={"backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}","borderRadius":"8px","fontSize":"13px"}
INPUT_STYLE={**DD_STYLE,"padding":"8px 12px","width":"100%","height":"38px"}
DELAY_CAUSE_LABELS={
    "CarrierDelay":"Carrier",
    "WeatherDelay":"Weather",
    "NASDelay":"Airspace / ATC",
    "SecurityDelay":"Security",
    "LateAircraftDelay":"Late aircraft",
    "ON_TIME":"On time / early",
    "UNASSIGNED":"Delay component unavailable",
}

def _airport_opts(df,col):
    vals=sorted(df[col].dropna().unique()) if col in df.columns else list(AIRPORTS.keys())
    return [{"label":v,"value":v} for v in vals]

def _airline_opts(df):
    vals=sorted(df["Operating_Airline"].dropna().unique()) if "Operating_Airline" in df.columns else list(AIRLINE_NAMES.keys())
    return [{"label":AIRLINE_NAMES.get(v,v),"value":v} for v in vals]

def _dominant_delay_cause(row):
    if int(row.get("Delayed", 0) or 0) != 1:
        return "ON_TIME"
    values = {
        cause: float(row.get(cause, 0) or 0)
        for cause in ["CarrierDelay", "WeatherDelay", "NASDelay", "SecurityDelay", "LateAircraftDelay"]
    }
    cause, minutes = max(values.items(), key=lambda item: item[1])
    return cause if minutes > 0 else "UNASSIGNED"

def _dominant_delay_reason(row):
    cause = row.get("_DominantCause") or _dominant_delay_cause(row)
    if cause in {"ON_TIME", "UNASSIGNED"}:
        return DELAY_CAUSE_LABELS[cause]
    minutes = float(row.get(cause, 0) or 0)
    return f"{DELAY_CAUSE_LABELS[cause]} ({minutes:.1f} min)"

def _format_delay(value):
    try:
        return f"{float(value):.1f}"
    except (TypeError, ValueError):
        return "0.0"

class LB:
    @staticmethod
    def navbar():
        return html.Div([html.Div([
            html.Div([html.A(html.Img(src="https://hassansalamb.dev/favicon.svg?v=2",alt="",**{"aria-hidden":"true"},
                                          style={"display":"block","width":"29px","height":"29px","borderRadius":"6px"}),
                                href="https://hassansalamb.dev",title="Back to hassansalamb.dev",
                                **{"aria-label":"Back to hassansalamb.dev"},style={"display":"grid","placeItems":"center","width":"36px","height":"36px","marginRight":"12px","border":f"1px solid {BORDER}","borderRadius":"7px","backgroundColor":BG,"textDecoration":"none"}),
                      html.Span("✈",style={"fontSize":"20px","color":CYAN,"marginRight":"12px"}),
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
        nav=[("◉","Live Airspace","live"),("▣","Historical Overview","overview"),
             ("⬡","Performance Explorer","performance"),("◈","Risk Analyzer","risk"),
             ("⌁","AI Delay Lab","ai_lab")]
        links=[html.Div(id=f"nav-{pid}",children=[
            html.Span(icon,style={"width":"20px","display":"inline-block","textAlign":"center","fontSize":"14px","marginRight":"10px","color":CYAN}),
            html.Span(label,style={"fontSize":"13px","whiteSpace":"nowrap","fontWeight":"500"})],
            style={"display":"flex","alignItems":"center","padding":"9px 14px","borderRadius":"8px","cursor":"pointer","color":MUTED,"marginBottom":"2px"},
            className="nav-item") for icon,label,pid in nav]
        airline_opts=[{"label":"All Airlines","value":"ALL"}]+[{"label":a,"value":a} for a in GULF_AIRLINES]
        return html.Div([
            html.Div("OPERATIONS VIEWS",style={"fontSize":"9px","fontWeight":"700","color":MUTED,"letterSpacing":"2px","padding":"20px 14px 8px"}),
            *links,
            html.Div(style={"height":"1px","backgroundColor":BORDER,"margin":"14px"}),
            html.Div("GULF MARKET",style={"fontSize":"9px","fontWeight":"700","color":CYAN,"letterSpacing":"2px","padding":"0 14px 6px"}),
            html.Div("Country → airport → airline",style={"fontSize":"10px","color":MUTED,"padding":"0 14px 10px","lineHeight":"1.4"}),
            html.Div([html.Div("Focus Country",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                      dcc.Dropdown(id="filter-gulf-country",
                                   options=[{"label":"🌍  All countries","value":"ALL"}] + [
                                       {"label":f"{v['flag']}  {country}","value":country}
                                       for country,v in GULF_COUNTRIES.items()
                                   ],value="Saudi Arabia",clearable=False,style=DD_STYLE,className="dst-dropdown")],
                     style={"padding":"0 10px","marginBottom":"14px"}),
            html.Div([html.Div("Gateway Airport",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                      dcc.Dropdown(id="filter-gulf-airport",value="ALL",clearable=False,style=DD_STYLE,className="dst-dropdown")],
                     style={"padding":"0 10px","marginBottom":"14px"}),
            html.Div([
                html.Div([html.Div("Airline",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                          dcc.Dropdown(id="filter-airline",options=airline_opts,value="ALL",clearable=False,style=DD_STYLE,className="dst-dropdown")],
                         style={"padding":"0 10px","marginBottom":"14px"}),
            ],id="airline-filter-section"),
            html.Div([
                html.Div(style={"height":"1px","backgroundColor":BORDER,"margin":"14px"}),
                html.Div("ANALYTICS WINDOW",style={"fontSize":"9px","fontWeight":"700","color":MUTED,"letterSpacing":"2px","padding":"0 14px 10px"}),
                html.Div([html.Div("Historical Year",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                          dcc.Dropdown(
                              id="filter-year",
                              options=[{"label":str(year),"value":year} for year in GULF_ANALYTICS_YEARS],
                              value=GULF_ANALYTICS_YEARS[-1],clearable=False,
                              style=DD_STYLE,className="dst-dropdown",
                          )],
                         style={"padding":"0 10px","marginBottom":"14px"}),
                html.Div([html.Div("Month Range",style={"color":MUTED,"fontSize":"11px","marginBottom":"8px"}),
                          dcc.RangeSlider(id="filter-month",min=1,max=12,step=1,value=[1,12],
                                          marks={1:"Jan",3:"Mar",6:"Jun",9:"Sep",12:"Dec"})],
                         style={"padding":"0 10px","marginBottom":"14px"}),
                html.Div([html.Div("Operational Status",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                          dcc.RadioItems(id="filter-delayed",
                                         options=[{"label":"  All Flights","value":"all"},{"label":"  Delayed Only","value":"delayed"}],
                                         value="all",style={"color":MUTED,"fontSize":"12px"},
                                         labelStyle={"display":"block","marginBottom":"4px"})],
                         style={"padding":"0 10px"}),
            ],id="analytics-filter-section"),
            html.Div("Live positions · Community ADS-B  |  Weather · Open-Meteo  |  Analytics · portfolio simulation",
                     style={"fontSize":"9px","color":MUTED,"padding":"16px 10px","lineHeight":"1.5"}),
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

    @staticmethod
    def intro(label,title,description,usage,source_note):
        return html.Div([
            html.Div(label,style={"fontSize":"9px","fontWeight":"700","color":CYAN,"letterSpacing":"1.6px","marginBottom":"5px"}),
            html.Div(title,style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginBottom":"5px"}),
            html.Div(description,style={"fontSize":"11px","color":MUTED,"lineHeight":"1.55"}),
            html.Div([html.Span("HOW TO USE · ",style={"fontWeight":"700","color":GREEN}),html.Span(usage)],style={"fontSize":"10px","color":TEXT,"marginTop":"8px"}),
            html.Div(source_note,style={"fontSize":"9px","color":MUTED,"marginTop":"5px"}),
        ],style={**CARD_STYLE,"padding":"14px 18px","borderLeft":f"3px solid {CYAN}","marginBottom":"12px"})

    def page_overview(self):
        g={"displayModeBar":False}
        return html.Div([
            self.intro("HISTORICAL OVERVIEW","Saudi & UAE portfolio performance",
                       "Summarizes historical-simulation flight volume, delay exposure, seasonality and route concentration for the selected market and year.",
                       "Choose a historical year, then compare countries, gateways or airlines and narrow the month range.",
                       "Data: 2023-2026 year-to-date portfolio simulation; this page contains no forecast or future-flight prediction."),
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

    def page_live(self):
        g={"displayModeBar":False,"scrollZoom":True}
        columns=[
            {"name":"Callsign","id":"callsign"},{"name":"From","id":"origin"},{"name":"To","id":"destination"},
            {"name":"Airline","id":"airline"},
            {"name":"Currently over","id":"current_area"},{"name":"Coordinates","id":"current_position"},
            {"name":"Nearest gateway","id":"nearest_airport"},
            {"name":"Distance km","id":"distance_to_airport_km"},
            {"name":"Altitude ft","id":"altitude_ft"},{"name":"Speed km/h","id":"speed_kmh"},
            {"name":"Heading","id":"heading"},{"name":"Registration country","id":"registration_country"},
            {"name":"Route match","id":"route_source"},
        ]
        return html.Div([
            self.intro("LIVE AIRSPACE","Aircraft being observed now",
                       "Shows current community ADS-B aircraft positions inside the selected Saudi/UAE portfolio boundary. Origin and destination are best-effort callsign route matches.",
                       "Choose all countries, one country, a nearest-gateway catchment or a recognized airline callsign prefix; aircraft color shows altitude and its nose follows the reported heading.",
                       "Positions: OpenSky primary / ADSB.lol fallback · Routes: ADSBDB community lookup · Weather: Open-Meteo. Route matches are not official schedules."),
            html.Div([
                html.Div([
                    html.Div("LIVE AIRSPACE",id="live-status",style={"fontSize":"11px","fontWeight":"700","letterSpacing":"1.5px","color":GREEN}),
                    html.Div("Current aircraft state vectors over the Gulf focus area",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginTop":"5px"}),
                    html.Div("Community ADS-B positions are not schedules, gates, airline delays, or proof of destination.",style={"fontSize":"11px","color":MUTED,"marginTop":"4px"}),
                ]),
                html.Div([
                    html.Div(id="live-count",style={"fontSize":"24px","fontWeight":"700","color":CYAN,"textAlign":"right"}),
                    html.Div(id="live-updated",style={"fontSize":"10px","color":MUTED,"textAlign":"right"}),
                ]),
            ],style={**CARD_STYLE,"display":"flex","justifyContent":"space-between","alignItems":"center","borderLeft":f"3px solid {GREEN}","marginBottom":"12px"}),
            html.Div(id="live-weather",style={"marginBottom":"12px"}),
            html.Div([
                dcc.Graph(id="chart-live-map",config=g,style={"height":"540px"}),
            ],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([
                html.Div("Aircraft observations",style={"fontSize":"14px","fontWeight":"700","color":TEXT,"marginBottom":"10px"}),
                dash_table.DataTable(
                    id="live-table",columns=columns,data=[],page_size=10,sort_action="native",
                    style_table={"overflowX":"auto"},
                    style_header={"backgroundColor":SURFACE,"color":MUTED,"border":f"1px solid {BORDER}","fontWeight":"700"},
                    style_cell={"backgroundColor":CARD,"color":TEXT,"border":f"1px solid {BORDER}","fontSize":"11px","padding":"8px","textAlign":"left"},
                    style_data_conditional=[{"if":{"row_index":"odd"},"backgroundColor":SURFACE}],
                ),
            ],style=CARD_STYLE),
        ])

    def page_performance(self):
        g={"displayModeBar":False}
        columns=[
            {"name":"Portfolio ID","id":"portfolio_flight"},
            {"name":"Flight","id":"flight"},
            {"name":"Date","id":"date"},
            {"name":"Time","id":"time"},
            {"name":"Route","id":"route"},
            {"name":"Airline","id":"airline"},
            {"name":"Status","id":"status"},
            {"name":"Dep delay","id":"dep_delay"},
            {"name":"Arr delay","id":"arr_delay"},
            {"name":"Dominant reason","id":"reason"},
            {"name":"Weather context","id":"weather_context"},
        ]
        hour_options=[{"label":"All hours","value":"ALL"}]+[
            {"label":f"{hour:02d}:00","value":hour} for hour in range(24)
        ]
        reason_options=[{"label":"All reasons","value":"ALL"}]+[
            {"label":label,"value":value}
            for value,label in DELAY_CAUSE_LABELS.items()
        ]
        tab_base={"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"10px 14px","fontSize":"12px","fontWeight":"700","cursor":"pointer","flex":"1","minWidth":"150px"}
        return html.Div([
            dcc.Store(id="performance-section",data="carrier"),
            self.intro("PERFORMANCE EXPLORER","Analyze carriers, gateways, routes and specific flights",
                       "Combines the portfolio's airline, airport and route analysis into one deep operational workspace.",
                       "Use the sidebar filters to move from market-level performance into specific carriers, gateways, routes and flight rows.",
                       "Data: portfolio simulation for demonstration and scenario analysis."),
            html.Div([
                html.Div([
                    html.Div("PERFORMANCE DATE RANGE",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px"}),
                    html.Div("One date selection updates carrier, gateway, route and flight drilldown results together.",
                             style={"fontSize":"13px","fontWeight":"700","color":TEXT,"marginTop":"5px"}),
                    html.Div("Leave both dates blank to use the sidebar Historical Year and Month Range.",
                             style={"fontSize":"11px","color":MUTED,"marginTop":"4px"}),
                ],style={"flex":"1.4","minWidth":"260px"}),
                html.Div([
                    html.Div("From date",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                    dcc.Input(id="performance-date-from",type="date",style=INPUT_STYLE),
                ],style={"flex":"1","minWidth":"160px"}),
                html.Div([
                    html.Div("Until date",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                    dcc.Input(id="performance-date-to",type="date",style=INPUT_STYLE),
                ],style={"flex":"1","minWidth":"160px"}),
                html.Div(id="performance-date-summary",style={"fontSize":"11px","color":MUTED,"textAlign":"right","minWidth":"190px"}),
            ],style={**CARD_STYLE,"display":"flex","gap":"12px","flexWrap":"wrap","alignItems":"flex-end","marginBottom":"12px","borderLeft":f"3px solid {CYAN}"}),
            html.Div([
                html.Div("PERFORMANCE VIEWS",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                html.Div([
                    html.Button("Carrier",id="perf-tab-carrier",n_clicks=0,style={**tab_base,"backgroundColor":CYAN,"color":BG}),
                    html.Button("Gateway / Route",id="perf-tab-network",n_clicks=0,style={**tab_base,"backgroundColor":SURFACE,"color":MUTED}),
                    html.Button("Flight Drilldown",id="perf-tab-flights",n_clicks=0,style={**tab_base,"backgroundColor":SURFACE,"color":MUTED}),
                ],style={"display":"flex","gap":"10px","flexWrap":"wrap"}),
            ],style={**CARD_STYLE,"padding":"14px","marginBottom":"12px"}),
            html.Div([
                html.Div("CARRIER PERFORMANCE",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                html.Div("Compare delay exposure by airline and see which operational factor dominates each carrier's delayed flights.",
                         style={"fontSize":"11px","color":MUTED,"marginBottom":"12px"}),
                html.Div([
                    html.Div([dcc.Graph(id="chart-airline-bar",config=g,style={"height":"340px"})],style={**CARD_STYLE,"flex":"1"}),
                    html.Div([dcc.Graph(id="chart-cause-stack",config=g,style={"height":"340px"})],style={**CARD_STYLE,"flex":"1"}),
                ],style={"display":"flex","gap":"12px","flexWrap":"wrap"}),
            ],id="performance-section-carrier",style={"marginBottom":"12px"}),
            html.Div([
                html.Div("GATEWAY AND ROUTE PERFORMANCE",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                html.Div("Move from airport pressure to origin-destination concentration without leaving the analysis context.",
                         style={"fontSize":"11px","color":MUTED,"marginBottom":"12px"}),
                html.Div([dcc.Graph(id="chart-airport-map",config=g,style={"height":"430px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
                html.Div([
                    html.Div([dcc.Graph(id="chart-heatmap",config=g,style={"height":"430px"})],style={**CARD_STYLE,"flex":"1"}),
                    html.Div([dcc.Graph(id="chart-bubble",config=g,style={"height":"430px"})],style={**CARD_STYLE,"flex":"1"}),
                ],style={"display":"flex","gap":"12px","flexWrap":"wrap","marginBottom":"12px"}),
            ],id="performance-section-network",style={"display":"none","marginBottom":"12px"}),
            html.Div([
                html.Div([
                    html.Div([
                        html.Div("FLIGHT DRILLDOWN",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px"}),
                        html.Div("Find the specific portfolio flights behind the airline delay charts",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginTop":"5px"}),
                        html.Div("Search by portfolio ID, flight number, route, airport or airline. The Performance date range controls this table and all charts above.",
                                 style={"fontSize":"11px","color":MUTED,"marginTop":"4px"}),
                    ]),
                    html.Div(id="flight-lookup-summary",style={"fontSize":"12px","color":MUTED,"textAlign":"right"}),
                ],style={"display":"flex","justifyContent":"space-between","gap":"16px","alignItems":"flex-start","marginBottom":"14px"}),
                html.Div([
                    html.Div([
                        html.Div("Search",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                        dcc.Input(id="lookup-flight-query",type="text",debounce=True,
                                  placeholder="e.g. DST-01234, SV1042, RUH-DXB",
                                  style=INPUT_STYLE),
                    ],style={"flex":"1.4","minWidth":"220px"}),
                    html.Div([
                        html.Div("Departure hour",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                        dcc.Dropdown(id="lookup-hour",options=hour_options,value="ALL",clearable=False,style=DD_STYLE,className="dst-dropdown"),
                    ],style={"flex":"1","minWidth":"150px"}),
                    html.Div([
                        html.Div("Dominant reason",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                        dcc.Dropdown(id="lookup-cause",options=reason_options,value="ALL",clearable=False,style=DD_STYLE,className="dst-dropdown"),
                    ],style={"flex":"1","minWidth":"190px"}),
                ],style={"display":"flex","gap":"12px","flexWrap":"wrap","marginBottom":"14px"}),
                dash_table.DataTable(
                    id="flight-lookup-table",columns=columns,data=[],page_size=12,sort_action="native",
                    style_table={"overflowX":"auto"},
                    style_header={"backgroundColor":SURFACE,"color":MUTED,"border":f"1px solid {BORDER}","fontWeight":"700"},
                    style_cell={"backgroundColor":CARD,"color":TEXT,"border":f"1px solid {BORDER}","fontSize":"11px","padding":"8px","textAlign":"left"},
                    style_data_conditional=[
                        {"if":{"row_index":"odd"},"backgroundColor":SURFACE},
                        {"if":{"filter_query":"{status} = \"Delayed\"","column_id":"status"},"color":AMBER,"fontWeight":"700"},
                        {"if":{"filter_query":"{reason} contains \"Weather\"","column_id":"reason"},"color":CYAN},
                    ],
                ),
            ],id="performance-section-flights",style={"display":"none",**CARD_STYLE}),
        ])

    def page_risk(self,df):
        ao=_airline_opts(df); oo=_airport_opts(df,"Origin"); do=_airport_opts(df,"Dest")
        dopt=[{"label":d,"value":d} for d in DAYS]
        dd=lambda lbl,fid,opts,val: html.Div([
            html.Div(lbl,style={"color":MUTED,"fontSize":"11px","marginBottom":"5px","fontWeight":"600"}),
            dcc.Dropdown(id=fid,options=opts,value=val,clearable=False,style=DD_STYLE,className="dst-dropdown"),
        ],style={"marginBottom":"14px"})
        return html.Div([
            self.intro("RISK ANALYZER","Explain a route's simulated operating risk",
                       "Combines observed simulation rates for the selected route, airline and weekday with current Open-Meteo conditions.",
                       "Choose origin, destination, airline and day, review live weather, then run the analyzer.",
                       "Output: explanatory portfolio scenario; not a prediction for an actual ticketed flight."),
            html.Div([
                html.Div("⚡  Flight Risk Analyzer",style={"fontSize":"16px","fontWeight":"700","color":TEXT,"marginBottom":"4px"}),
                html.Div("Select a Saudi or UAE flight — live weather fetched automatically from Open-Meteo API",
                         style={"fontSize":"12px","color":MUTED,"marginBottom":"20px"}),
                html.Div([
                    html.Div([dd("Origin Airport","risk-origin",oo,oo[0]["value"] if oo else "RUH"),
                              dd("Destination Airport","risk-dest",do,do[1]["value"] if len(do)>1 else "DXB")],style={"flex":"1"}),
                    html.Div([dd("Airline","risk-airline",ao,ao[0]["value"] if ao else "Riyadh Air"),
                              dd("Day of Week","risk-day",dopt,"Monday")],style={"flex":"1"}),
                ],style={"display":"flex","gap":"24px","marginBottom":"16px"}),
                html.Div(id="weather-preview",style={"marginBottom":"16px"}),
                html.Button("Analyze Flight Risk ⚡",id="btn-risk",n_clicks=0,style={
                    "backgroundColor":CYAN,"color":BG,"border":"none","borderRadius":"8px",
                    "padding":"10px 28px","fontSize":"13px","fontWeight":"700","cursor":"pointer"}),
            ],style=CARD_STYLE),
            html.Div(id="risk-result",style={"marginTop":"16px"}),
        ])

    def page_ml(self, status, charts, include_intro=True):
        if not status.get("available"):
            children = []
            if include_intro:
                children.append(self.intro(
                    "MODEL EVIDENCE", "Model governance and evaluation",
                    "Shows which delay model is serving predictions, how it compares with the baseline and whether its probabilities are calibrated.",
                    "Start the prediction API or deploy the API container to load the model artifact.",
                    "No heuristic is presented as a trained model.",
                ))
            children.append(
                html.Div([
                    html.Div("MODEL UNAVAILABLE",style={"fontSize":"11px","fontWeight":"700","color":AMBER,"letterSpacing":"1.4px"}),
                    html.Div(status.get("reason","Model artifact could not be loaded."),style={"fontSize":"13px","color":TEXT,"marginTop":"8px"}),
                ],style={**CARD_STYLE,"borderLeft":f"3px solid {AMBER}"}),
            )
            return html.Div(children)

        metrics = status.get("metrics", {})
        champion_metrics = metrics.get(status.get("champion"), {})
        reliability_score = status.get("reliability_score", 0)
        reliability_label = status.get("reliability_label", "portfolio score unavailable")
        metric_rows = [
            {
                "model": model,
                "roc_auc": values.get("roc_auc"),
                "pr_auc": values.get("pr_auc"),
                "brier": values.get("brier"),
                "recall": values.get("recall"),
            }
            for model, values in metrics.items()
        ]
        summary_card = lambda label, value, note, color: html.Div([
            html.Div(label,style={"fontSize":"9px","fontWeight":"700","letterSpacing":"1.4px","color":MUTED}),
            html.Div(value,style={"fontSize":"26px","fontWeight":"700","color":color,"margin":"6px 0"}),
            html.Div(note,style={"fontSize":"10px","color":MUTED,"lineHeight":"1.4"}),
        ],style={**CARD_STYLE,"flex":"1","minWidth":"150px","padding":"16px"})
        inference_available = status.get("inference_available", True)
        deployment_status_label = "● MODEL API ONLINE" if inference_available else "● MODEL METADATA LOADED"
        deployment_status_color = GREEN if inference_available else AMBER
        deployment_status_note = status.get(
            "serving_note",
            "FastAPI inference service is reachable.",
        )
        deployment_steps = [
            ("1", "Offline training", "2023 fit · 2024 calibration · 2025 evaluation"),
            ("2", "Versioned artifact", status.get("version", "Unknown version")),
            ("3", "FastAPI inference", "Artifact loaded once and retained in API memory"),
            ("4", "Dashboard consumer", "AI Delay Lab calls POST /predict/gulf"),
        ]
        children = []
        if include_intro:
            children.append(self.intro(
                "MODEL EVIDENCE", "Model score and reliability",
                "Separates model quality, explainability and deployment health from operational analytics and scenario inputs.",
                "Review the score, baseline comparison, calibration and feature importance, then run current or future what-if scenarios.",
                status.get("limitations","Portfolio simulation; not an official airline forecast."),
            ))
        else:
            children.append(html.Div([
                html.Div("MODEL EVIDENCE",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px"}),
                html.Div("Model status, reliability, calibration and feature importance",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginTop":"5px"}),
                html.Div(status.get("limitations","Portfolio simulation; not an official airline forecast."),
                         style={"fontSize":"11px","color":MUTED,"marginTop":"4px"}),
            ],style={"margin":"4px 0 12px"}))
        children.extend([
            html.Div([
                summary_card("CHAMPION", "CatBoost", status.get("algorithm",""), CYAN),
                summary_card("MODEL SCORE", f"{reliability_score}/100", reliability_label, AMBER),
                summary_card("ROC-AUC", f"{champion_metrics.get('roc_auc',0):.3f}", "Ranking quality on untouched 2025 data", GREEN),
                summary_card("BRIER SCORE", f"{champion_metrics.get('brier',0):.3f}", "Probability error · lower is better", PURPLE),
                summary_card("TEST SET", f"{status.get('test_rows',0):,}", "2025 simulated operations", TEXT),
            ],style={"display":"flex","gap":"12px","flexWrap":"wrap","marginBottom":"12px"}),
            html.Div([
                html.Div([
                    html.Div("MODEL CARD",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                    html.Div(f"{status.get('champion')} · {status.get('version')}",style={"fontSize":"15px","fontWeight":"700","color":TEXT}),
                    html.Div(f"Data: {status.get('data_scope')}",style={"fontSize":"11px","color":MUTED,"marginTop":"8px"}),
                    html.Div(f"Fit {status.get('fit_year')} → calibrate {status.get('calibration_year')} → evaluate {status.get('evaluation_year')}",style={"fontSize":"11px","color":MUTED,"marginTop":"5px"}),
                    html.Div(f"Rows: {status.get('training_rows',0):,} fit · {status.get('calibration_rows',0):,} calibration · {status.get('test_rows',0):,} evaluation",style={"fontSize":"11px","color":MUTED,"marginTop":"5px"}),
                    html.Div(status.get("selection_reason",""),style={"fontSize":"10px","color":CYAN,"marginTop":"10px","lineHeight":"1.5"}),
                ],style={**CARD_STYLE,"flex":"1"}),
                html.Div([
                    html.Div("RELIABILITY LENS",style={"fontSize":"10px","fontWeight":"700","color":AMBER,"letterSpacing":"1.4px","marginBottom":"10px"}),
                    html.Div(f"{reliability_score}/100 · {reliability_label}",style={"fontSize":"15px","fontWeight":"700","color":TEXT}),
                    html.Div(status.get("reliability_note",""),style={"fontSize":"11px","color":MUTED,"marginTop":"8px","lineHeight":"1.5"}),
                    html.Div(f"Calibration gap: {status.get('calibration_gap',0):.3f}",style={"fontSize":"10px","color":AMBER,"marginTop":"10px"}),
                ],style={**CARD_STYLE,"flex":"1","borderLeft":f"3px solid {AMBER}"}),
                html.Div([
                    html.Div("DEPLOYMENT STATUS",style={"fontSize":"10px","fontWeight":"700","color":GREEN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                    html.Div(deployment_status_label,style={"fontSize":"13px","fontWeight":"700","color":deployment_status_color}),
                    html.Div(deployment_status_note,style={"fontSize":"11px","color":MUTED,"marginTop":"8px"}),
                ],style={**CARD_STYLE,"flex":"1","borderLeft":f"3px solid {deployment_status_color}"}),
            ],style={"display":"flex","gap":"12px","marginBottom":"12px"}),
            html.Div([dcc.Graph(figure=charts.ml_metric_comparison(metrics),config={"displayModeBar":False},style={"height":"360px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([
                html.Div([dcc.Graph(figure=charts.ml_feature_importance(status.get("feature_importance",[])),config={"displayModeBar":False},style={"height":"390px"})],style={**CARD_STYLE,"flex":"1"}),
                html.Div([dcc.Graph(figure=charts.ml_calibration(status.get("calibration",[])),config={"displayModeBar":False},style={"height":"390px"})],style={**CARD_STYLE,"flex":"1"}),
            ],style={"display":"flex","gap":"12px","marginBottom":"12px"}),
            html.Div([
                html.Div("EVALUATION TABLE",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                dash_table.DataTable(
                    data=metric_rows,
                    columns=[
                        {"name":"Model","id":"model"},{"name":"ROC-AUC ↑","id":"roc_auc"},
                        {"name":"PR-AUC ↑","id":"pr_auc"},{"name":"Brier ↓","id":"brier"},
                        {"name":"Recall ↑","id":"recall"},
                    ],
                    style_header={"backgroundColor":SURFACE,"color":MUTED,"border":f"1px solid {BORDER}","fontWeight":"700"},
                    style_cell={"backgroundColor":CARD,"color":TEXT,"border":f"1px solid {BORDER}","fontSize":"11px","padding":"9px","textAlign":"left"},
                ),
            ],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([
                html.Div("DEPLOYMENT PATH",style={"fontSize":"10px","fontWeight":"700","color":PURPLE,"letterSpacing":"1.4px","marginBottom":"12px"}),
                html.Div([
                    html.Div([
                        html.Div(number,style={"width":"24px","height":"24px","borderRadius":"50%","backgroundColor":PURPLE,"color":TEXT,"display":"flex","alignItems":"center","justifyContent":"center","fontSize":"10px","fontWeight":"700"}),
                        html.Div([html.Div(title,style={"fontSize":"12px","fontWeight":"700","color":TEXT}),html.Div(note,style={"fontSize":"10px","color":MUTED,"marginTop":"4px","lineHeight":"1.4"})],style={"marginLeft":"10px"}),
                    ],style={"display":"flex","alignItems":"flex-start","flex":"1","minWidth":"180px"})
                    for number,title,note in deployment_steps
                ],style={"display":"flex","gap":"18px","flexWrap":"wrap"}),
            ],style=CARD_STYLE),
        ])
        return html.Div(children)

    def page_ai_lab(self, status, charts):
        fld=lambda lbl,ph,fid,val,typ="number": html.Div([
            html.Div(lbl,style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
            dcc.Input(id=fid,type=typ,placeholder=ph,value=val,debounce=True,style={
                "width":"100%","backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}",
                "borderRadius":"8px","padding":"8px 12px","fontSize":"13px","boxSizing":"border-box"})],
            style={"marginBottom":"12px"})
        return html.Div([
            self.intro("AI DELAY LAB","Test a scenario and inspect the model behind it",
                       "Uses the calibrated CatBoost model served by FastAPI to estimate delay probability from portfolio route, carrier, calendar and weather features.",
                       "Change the route, carrier, date, departure hour and weather inputs, then review the model evidence underneath the result.",
                       "Output: portfolio what-if model; not official airline or airport status."),
            html.Div([
                html.Div("Scenario inputs",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginBottom":"4px"}),
                html.Div("Future dates are allowed for what-if scenarios; this is not a scheduled-flight forecast.",style={"fontSize":"12px","color":MUTED,"marginBottom":"20px"}),
                html.Div([
                    html.Div([
                        html.Div("Origin",style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
                        dcc.Dropdown(id="pred-origin",options=[{"label":code,"value":code} for code in GULF_COUNTRIES["Saudi Arabia"]["airports"]|GULF_COUNTRIES["United Arab Emirates"]["airports"]],value="RUH",clearable=False,style=DD_STYLE,className="dst-dropdown"),
                        html.Div("Destination",style={"color":MUTED,"fontSize":"11px","margin":"12px 0 5px"}),
                        dcc.Dropdown(id="pred-dest",options=[{"label":code,"value":code} for code in GULF_COUNTRIES["Saudi Arabia"]["airports"]|GULF_COUNTRIES["United Arab Emirates"]["airports"]],value="DXB",clearable=False,style=DD_STYLE,className="dst-dropdown"),
                        html.Div("Airline",style={"color":MUTED,"fontSize":"11px","margin":"12px 0 5px"}),
                        dcc.Dropdown(id="pred-airline",options=[{"label":name,"value":name} for name in GULF_AIRLINES],value="Riyadh Air",clearable=False,style=DD_STYLE,className="dst-dropdown"),
                        html.Div("Flight date",style={"color":MUTED,"fontSize":"11px","margin":"12px 0 5px"}),
                        dcc.Input(id="pred-date",type="date",value=date.today().isoformat(),style={
                            "width":"100%","backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}",
                            "borderRadius":"8px","padding":"8px 12px","fontSize":"13px","boxSizing":"border-box"}),
                    ],style={"flex":"1"}),
                    html.Div([fld("Departure hour (0-23)","18","pred-hour",18),fld("Wind (km/h)","25","pred-wind",25),
                              fld("Precipitation (mm)","0","pred-precip",0),fld("Cloud cover (%)","20","pred-cloud",20)],style={"flex":"1"}),
                ],style={"display":"flex","gap":"24px","flexWrap":"wrap"}),
                html.Button("Run Scenario Prediction",id="btn-predict",n_clicks=0,style={
                    "backgroundColor":CYAN,"color":BG,"border":"none","borderRadius":"8px",
                    "padding":"10px 28px","fontSize":"13px","fontWeight":"700","cursor":"pointer","marginTop":"8px"}),
                html.Div(id="prediction-result",style={"marginTop":"20px"}),
            ],style={**CARD_STYLE,"maxWidth":"860px","marginBottom":"16px"}),
            self.page_ml(status, charts, include_intro=False),
        ])


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
                    html.Div(id="page-content"),
                ],style={"flex":"1","padding":"20px 24px","overflowY":"auto","backgroundColor":BG,"minHeight":"calc(100vh - 56px)"}),
            ],style={"display":"flex"}),
            self.lb.footer(),
        ],style={"fontFamily":"'DM Sans',sans-serif","backgroundColor":BG})

    def _callbacks(self):
        app=self.app; charts=self.charts; lb=self.lb

        @app.callback(Output("api-badge","children"),Input("tick","n_intervals"))
        def badge(_):
            c=GREEN; l="● HYBRID GULF DATA"
            return html.Div(l,style={"fontSize":"10px","fontWeight":"700","color":c,"border":f"1px solid {c}","borderRadius":"20px","padding":"3px 10px"})

        app.clientside_callback(
            "function(a,b,c,d,e,cur){const t=dash_clientside.callback_context.triggered;if(!t||!t.length)return cur;return t[0].prop_id.split('.')[0].replace('nav-','');}",
            Output("page","data"),
            [Input(f"nav-{p}","n_clicks") for p in ["live","overview","performance","risk","ai_lab"]],
            State("page","data"),prevent_initial_call=True)

        @app.callback(
            Output("airline-filter-section","style"),
            Output("analytics-filter-section","style"),
            Input("page","data"),
        )
        def contextual_sidebar(page):
            analytics_pages={"overview","performance"}
            airline_pages=analytics_pages | {"live"}
            airline_visible={} if page in airline_pages else {"display":"none"}
            analytics_visible={} if page in analytics_pages else {"display":"none"}
            return airline_visible, analytics_visible

        def _f(country,airport,airline,year,months,delayed):
            market = GULF_COUNTRIES.get(country, {})
            valid_airports = (
                {code for item in GULF_COUNTRIES.values() for code in item["airports"]}
                if country == "ALL" else set(market.get("airports", {}))
            )
            valid_airlines = GULF_AIRLINES if country == "ALL" else market.get("airlines", [])
            if airport not in valid_airports:
                airport = "ALL"
            if airline not in valid_airlines and airline != "ALL":
                airline = "ALL"
            df=get_gulf_flights_df(country,airport)
            if airline and airline!="ALL" and "Operating_Airline" in df.columns: df=df[df["Operating_Airline"]==airline]
            if year and "Year" in df.columns: df=df[df["Year"]==int(year)]
            if "Month" in df.columns: df=df[df["Month"].between(months[0],months[1])]
            if delayed=="delayed" and "Delayed" in df.columns: df=df[df["Delayed"]==1]
            return df

        ins=[Input("filter-gulf-country","value"),Input("filter-gulf-airport","value"),Input("filter-airline","value"),Input("filter-year","value"),Input("filter-month","value"),Input("filter-delayed","value")]
        performance_ins=[*ins,Input("performance-date-from","value"),Input("performance-date-to","value")]

        def _performance_df(country,airport,airline,year,months,delayed,date_from,date_to):
            if not date_from and not date_to:
                return _f(country,airport,airline,year,months,delayed)

            df=_f(country,airport,airline,None,[1,12],delayed).copy()
            if df.empty or "FlightDate" not in df.columns:
                return df

            start=pd.to_datetime(date_from).date() if date_from else None
            end=pd.to_datetime(date_to).date() if date_to else None
            if start and end and start > end:
                start,end=end,start

            flight_dates=pd.to_datetime(df["FlightDate"]).dt.date
            if start:
                df=df[flight_dates >= start]
                flight_dates=flight_dates.loc[df.index]
            if end:
                df=df[flight_dates <= end]
            return df

        def _performance_scope_summary(country,airport,airline,year,months,delayed,date_from,date_to):
            df=_performance_df(country,airport,airline,year,months,delayed,date_from,date_to)
            total=len(df)
            delayed_count=int(df["Delayed"].sum()) if total and "Delayed" in df.columns else 0
            if date_from or date_to:
                start=date_from or "first available"
                end=date_to or "latest available"
                return f"Custom range · {start} to {end} · {total:,} flights · {delayed_count:,} delayed"
            month_label=f"months {months[0]}-{months[1]}" if months else "all months"
            return f"Sidebar timeline · {year} · {month_label} · {total:,} flights · {delayed_count:,} delayed"

        @app.callback(Output("page-content","children"),Output("page-header","children"),
                      Input("page","data"),*ins)
        def render(page,country,airport,a,year,m,d):
            df=_f(country,airport,a,year,m,d)
            titles={
                "live":"◉ Live Gulf Airspace",
                "overview":"Historical Operations · Portfolio Simulation",
                "performance":"Performance Explorer",
                "risk":"◈ Gulf Flight Risk Analyzer",
                "ai_lab":"⌁ AI Delay Lab",
            }
            pages={"live":lb.page_live,"overview":lb.page_overview,"performance":lb.page_performance}
            if page == "risk":
                content = lb.page_risk(df)
            elif page == "ai_lab":
                content = lb.page_ai_lab(get_ml_status(API_BASE_URL), charts)
            else:
                content = pages.get(page,lb.page_overview)()
            return content,titles.get(page,"Dashboard")

        @app.callback(
            Output("filter-gulf-airport", "options"),
            Output("filter-gulf-airport", "value"),
            Input("filter-gulf-country", "value"),
        )
        def gulf_airport_options(country):
            if country == "ALL":
                options = [{"label": "All gateways", "value": "ALL"}]
                for market_country, market in GULF_COUNTRIES.items():
                    options.extend([
                        {"label": f"{code} — {name} ({market_country})", "value": code}
                        for code, name in market["airports"].items()
                    ])
                return options, "ALL"
            if country not in GULF_COUNTRIES:
                return [], None
            options = [{"label": "All gateways", "value": "ALL"}] + [
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

        @app.callback(Output("kpi-row","children"),*ins)
        def kpis(country,airport,a,year,m,d):
            df=_f(country,airport,a,year,m,d); t=len(df)
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
        @app.callback(Output("performance-date-summary","children"),*performance_ins)
        def performance_scope(*args): return _performance_scope_summary(*args)

        app.clientside_callback(
            """
            function(carrier,network,flights,current){
                const triggered=dash_clientside.callback_context.triggered;
                if(!triggered || !triggered.length){
                    return current || "carrier";
                }
                const id=triggered[0].prop_id.split(".")[0];
                if(id==="perf-tab-network"){return "network";}
                if(id==="perf-tab-flights"){return "flights";}
                return "carrier";
            }
            """,
            Output("performance-section","data"),
            Input("perf-tab-carrier","n_clicks"),
            Input("perf-tab-network","n_clicks"),
            Input("perf-tab-flights","n_clicks"),
            State("performance-section","data"),
            prevent_initial_call=True,
        )

        @app.callback(
            Output("perf-tab-carrier","style"),
            Output("perf-tab-network","style"),
            Output("perf-tab-flights","style"),
            Output("performance-section-carrier","style"),
            Output("performance-section-network","style"),
            Output("performance-section-flights","style"),
            Input("performance-section","data"),
        )
        def performance_section_styles(section):
            section=section or "carrier"
            base={"border":f"1px solid {BORDER}","borderRadius":"8px","padding":"10px 14px","fontSize":"12px","fontWeight":"700","cursor":"pointer","flex":"1","minWidth":"150px"}
            active={**base,"backgroundColor":CYAN,"color":BG}
            inactive={**base,"backgroundColor":SURFACE,"color":MUTED}
            carrier_style={"marginBottom":"12px"} if section=="carrier" else {"display":"none","marginBottom":"12px"}
            network_style={"marginBottom":"12px"} if section=="network" else {"display":"none","marginBottom":"12px"}
            flights_style={**CARD_STYLE} if section=="flights" else {**CARD_STYLE,"display":"none"}
            return (
                active if section=="carrier" else inactive,
                active if section=="network" else inactive,
                active if section=="flights" else inactive,
                carrier_style,network_style,flights_style,
            )

        @app.callback(Output("chart-airline-bar","figure"),*performance_ins)
        def ca(*args): return charts.airline_delay_bar(_performance_df(*args))
        @app.callback(Output("chart-cause-stack","figure"),*performance_ins)
        def cc(*args): return charts.delay_cause_stack(_performance_df(*args))

        @app.callback(
            Output("flight-lookup-summary","children"),
            Output("flight-lookup-table","data"),
            *performance_ins,
            Input("lookup-flight-query","value"),
            Input("lookup-hour","value"),
            Input("lookup-cause","value"),
        )
        def flight_lookup(country,airport,a,year,m,d,date_from,date_to,query,hour,cause):
            df=_performance_df(country,airport,a,year,m,d,date_from,date_to).copy()
            if df.empty:
                return "No matching portfolio flights", []

            df["_DominantCause"]=df.apply(_dominant_delay_cause,axis=1)

            if hour not in (None,"ALL",""):
                df=df[df["DepartureHour"]==int(hour)]
            if cause not in (None,"ALL",""):
                df=df[df["_DominantCause"]==cause]

            q=(query or "").strip().upper()
            if q:
                compact=q.replace(" ","")
                routes=(df["Origin"].astype(str)+"-"+df["Dest"].astype(str)).str.upper()
                reverse_routes=(df["Dest"].astype(str)+"-"+df["Origin"].astype(str)).str.upper()
                searchable=(
                    df["PortfolioFlightId"].astype(str).str.upper()+" "+
                    df["FlightCode"].astype(str).str.upper()+" "+
                    df["Operating_Airline"].astype(str).str.upper()+" "+
                    df["Origin"].astype(str).str.upper()+" "+
                    df["Dest"].astype(str).str.upper()+" "+
                    routes+" "+reverse_routes
                )
                df=df[searchable.str.contains(q,regex=False) | routes.str.contains(compact,regex=False)]

            if df.empty:
                return "No matching portfolio flights", []

            df=df.sort_values(["FlightDate","DepartureHour","DepartureMinute"],ascending=[False,True,True])
            total=len(df)
            rows=[]
            for _,row in df.iterrows():
                time_label=f"{int(row['DepartureHour']):02d}:{int(row.get('DepartureMinute',0)):02d}"
                status="Delayed" if int(row.get("Delayed",0) or 0)==1 else "On time"
                weather_context=(
                    f"Wind {float(row.get('WindKmh',0) or 0):.1f} km/h, "
                    f"rain {float(row.get('PrecipitationMm',0) or 0):.1f} mm, "
                    f"cloud {float(row.get('CloudCoverPct',0) or 0):.0f}%"
                )
                rows.append({
                    "portfolio_flight":row.get("PortfolioFlightId"),
                    "flight":row.get("FlightCode"),
                    "date":pd.to_datetime(row["FlightDate"]).strftime("%Y-%m-%d"),
                    "time":time_label,
                    "route":f"{row.get('Origin')} -> {row.get('Dest')}",
                    "airline":row.get("Operating_Airline"),
                    "status":status,
                    "dep_delay":f"{_format_delay(row.get('DepDelay'))} min",
                    "arr_delay":f"{_format_delay(row.get('ArrDelay'))} min",
                    "reason":_dominant_delay_reason(row),
                    "weather_context":weather_context,
                })
            shown=len(rows)
            delayed_count=int((df["Delayed"]==1).sum()) if "Delayed" in df.columns else 0
            return f"{total:,} matches · {delayed_count:,} delayed · showing all {shown:,}", rows

        @app.callback(Output("chart-heatmap","figure"),*performance_ins)
        def chm(*args): return charts.route_heatmap_top(_performance_df(*args))
        @app.callback(Output("chart-bubble","figure"),*performance_ins)
        def cb(*args): return charts.top_routes_bubble(_performance_df(*args))

        @app.callback(Output("chart-airport-map","figure"),*performance_ins)
        def c_map(*args): return charts.airport_map(_performance_df(*args))

        @app.callback(
            Output("chart-live-map","figure"),Output("live-table","data"),
            Output("live-status","children"),Output("live-status","style"),
            Output("live-count","children"),Output("live-updated","children"),
            Output("live-weather","children"),
            Input("tick","n_intervals"),Input("filter-gulf-country","value"),
            Input("filter-gulf-airport","value"),Input("filter-airline","value"),
        )
        def live_airspace(_, country, airport, airline):
            payload=get_live_flights(country,airport)
            rows=payload.get("data",[])
            if airline and airline != "ALL":
                rows=[row for row in rows if row.get("airline") == airline]
            is_live=bool(payload.get("is_live"))
            color=GREEN if is_live else AMBER
            updated=payload.get("last_updated")
            if updated:
                try:
                    updated=pd.to_datetime(updated,utc=True).strftime("Updated %H:%M:%S UTC")
                except Exception:
                    updated=f"Updated {updated}"
            else:
                updated="No current snapshot"
            source=payload.get("source","OpenSky Network")
            provider="ADSB.LOL" if "ADSB.lol" in source else "OPENSKY"
            status=f"● LIVE · {provider}" if is_live else "● LIVE FEED UNAVAILABLE"
            updated=f"{updated} · {source} · dashboard checks every 30s"
            weather=get_weather(airport) if airport and airport != "ALL" else None
            if weather:
                weather_card=html.Div([
                    html.Div(f"{airport} · LIVE WEATHER",style={"fontSize":"10px","fontWeight":"700","color":CYAN,"letterSpacing":"1.2px"}),
                    html.Div([
                        html.Span(f"🌡 {weather['temp']}°C"),html.Span(f"💨 {weather['wind_speed']} km/h"),
                        html.Span(f"🌧 {weather['precip']} mm"),html.Span(f"☁ {weather['cloud_cover']}/8"),
                    ],style={"display":"flex","gap":"22px","fontSize":"12px","color":TEXT,"marginTop":"8px"}),
                    html.Div("Source: Open-Meteo",style={"fontSize":"9px","color":MUTED,"marginTop":"6px"}),
                ],style={**CARD_STYLE,"padding":"14px 18px","borderLeft":f"3px solid {CYAN}"})
            else:
                weather_card=html.Div("Select a gateway airport to add current Open-Meteo weather.",style={**CARD_STYLE,"fontSize":"11px","color":MUTED})
            table_rows=[{key:row.get(key) for key in [
                "callsign","origin","destination","airline","current_area","current_position","nearest_airport",
                "distance_to_airport_km","altitude_ft","speed_kmh","heading",
                "registration_country","route_source",
            ]} for row in rows]
            return (
                charts.live_aircraft_map(rows,country,airport),table_rows,status,
                {"fontSize":"11px","fontWeight":"700","letterSpacing":"1.5px","color":color},
                f"{len(rows)} aircraft",updated,weather_card,
            )

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

        @app.callback(
            Output("prediction-result","children"),Input("btn-predict","n_clicks"),
            State("pred-origin","value"),State("pred-dest","value"),State("pred-airline","value"),
            State("pred-date","value"),
            State("pred-hour","value"),State("pred-wind","value"),State("pred-precip","value"),State("pred-cloud","value"),
            prevent_initial_call=True,
        )
        def predict_scenario(_,origin,dest,airline,flight_date,hour,wind,precip,cloud):
            if origin==dest:
                return html.Div("Select two different Gulf airports.",style={"color":AMBER})
            if any(value is None for value in [flight_date,hour,wind,precip,cloud]):
                return html.Div("Enter the date and all four operating-condition inputs.",style={"color":AMBER})
            frame=get_gulf_flights_df()
            route=frame[(frame["Origin"]==origin)&(frame["Dest"]==dest)]
            distance=float(route["Distance"].median() if not route.empty else frame["Distance"].median())
            payload={
                "origin":origin,"destination":dest,"airline":airline,
                "flight_date":flight_date,"distance":distance,
                "departure_hour":int(hour),"wind_kmh":float(wind),
                "precipitation_mm":float(precip),"cloud_cover_pct":float(cloud),
            }
            prediction=predict_gulf_delay(API_BASE_URL,payload,frame)
            probability=float(prediction["delay_probability"])
            color=GREEN if probability<0.30 else AMBER if probability<0.60 else RED
            label=prediction["risk_band"]
            fallback_note = prediction.get("fallback_reason")
            return html.Div([
                html.Div(f"{label} DELAY RISK",style={"fontSize":"11px","fontWeight":"700","letterSpacing":"1.4px","color":color}),
                html.Div(f"{probability*100:.1f}%",style={"fontSize":"38px","fontWeight":"700","color":color,"margin":"5px 0"}),
                html.Div(f"{airline} · {origin} → {dest} · {flight_date} at {int(hour):02d}:00",style={"fontSize":"12px","color":TEXT}),
                html.Div(f"{prediction['algorithm']} · {prediction['model_version']}",style={"fontSize":"10px","color":CYAN,"marginTop":"8px"}),
                html.Div(prediction["limitations"],style={"fontSize":"10px","color":MUTED,"marginTop":"5px"}),
                html.Div(f"API note: {fallback_note}",style={"fontSize":"10px","color":AMBER,"marginTop":"6px"}) if fallback_note else None,
            ],style={**CARD_STYLE,"borderLeft":f"3px solid {color}"})



    def run(self,debug=False,port=8050):
        self.app.run(debug=debug,host="0.0.0.0",port=port)

if __name__=="__main__":
    App().run(debug=False,port=8050)
