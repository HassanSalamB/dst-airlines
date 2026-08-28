"""
app.py — DST Airlines Dashboard v4 — FINAL
"""
from datetime import date

import requests
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
from weather import get_weather

BG="#0a0e1a"; CARD="#0f1523"; SURFACE="#161d2e"; BORDER="#1e2a3a"
CYAN="#00d4ff"; BLUE="#4a9eff"; PURPLE="#8b5cf6"; GREEN="#10b981"
AMBER="#f59e0b"; RED="#ef4444"; TEXT="#f1f5f9"; MUTED="#64748b"
SIDEBAR_W="220px"
DAYS=["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
AIRLINE_NAMES={name:name for name in GULF_AIRLINES}
CARD_STYLE={"backgroundColor":CARD,"border":f"1px solid {BORDER}","borderRadius":"12px","padding":"20px"}
DD_STYLE={"backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}","borderRadius":"8px","fontSize":"13px"}

def get_ml_status():
    try:
        response = requests.get(f"{API_BASE_URL}/model/gulf/status", timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        return {"available": False, "reason": f"Prediction API unavailable: {exc}"}

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
        nav=[("◉","Live Airspace","live"),("▣","Historical Overview","overview"),
             ("✈","Airlines","airlines"),("🗺","Airports","map"),
             ("⬡","Routes","routes"),("▲","Trends","trends"),
             ("◈","Risk Analyzer","risk"),("◆","ML Intelligence","ml"),
             ("⌁","Prediction Lab","predict")]
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
            html.Div("Live positions · OpenSky  |  Weather · Open-Meteo  |  Analytics · portfolio simulation",
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
                       "Data: 2023–2025 portfolio simulation; this page contains no forecast or future-flight prediction."),
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
            {"name":"Currently over","id":"current_area"},{"name":"Coordinates","id":"current_position"},
            {"name":"Nearest gateway","id":"nearest_airport"},
            {"name":"Distance km","id":"distance_to_airport_km"},
            {"name":"Altitude ft","id":"altitude_ft"},{"name":"Speed km/h","id":"speed_kmh"},
            {"name":"Heading","id":"heading"},{"name":"Registration country","id":"registration_country"},
            {"name":"Route match","id":"route_source"},
        ]
        return html.Div([
            self.intro("LIVE AIRSPACE","Aircraft being observed now",
                       "Shows current OpenSky aircraft positions inside the selected Saudi/UAE portfolio boundary. Origin and destination are best-effort callsign route matches.",
                       "Choose all countries, one country or a nearest-gateway catchment; aircraft color shows altitude, its nose follows the reported heading, and a dotted airport-to-airport line appears only for complete route matches.",
                       "Positions: OpenSky · Routes: ADSBDB community lookup · Weather: Open-Meteo. Route matches are not official schedules."),
            html.Div([
                html.Div([
                    html.Div("LIVE AIRSPACE",id="live-status",style={"fontSize":"11px","fontWeight":"700","letterSpacing":"1.5px","color":GREEN}),
                    html.Div("Current aircraft state vectors over the Gulf focus area",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginTop":"5px"}),
                    html.Div("OpenSky positions are not schedules, gates, airline delays, or proof of destination.",style={"fontSize":"11px","color":MUTED,"marginTop":"4px"}),
                ]),
                html.Div([
                    html.Div(id="live-count",style={"fontSize":"24px","fontWeight":"700","color":CYAN,"textAlign":"right"}),
                    html.Div(id="live-updated",style={"fontSize":"10px","color":MUTED,"textAlign":"right"}),
                ]),
            ],style={**CARD_STYLE,"display":"flex","justifyContent":"space-between","alignItems":"center","borderLeft":f"3px solid {GREEN}","marginBottom":"12px"}),
            html.Div(id="live-weather",style={"marginBottom":"12px"}),
            html.Div([
                dcc.Graph(id="chart-live-map",config=g,style={"height":"540px"}),
                html.Div(
                    "Dotted line = matched origin airport to destination airport. It appears only when ADSBDB supplies both airport coordinates and is a straight reference—not the aircraft's filed or actually flown path.",
                    style={"fontSize":"9px","color":MUTED,"padding":"0 14px 12px","lineHeight":"1.5"},
                ),
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

    def page_airlines(self):
        g={"displayModeBar":False}
        return html.Div([
            self.intro("AIRLINE PERFORMANCE","Compare Gulf portfolio carriers",
                       "Benchmarks simulated delay rates and the modeled contribution of carrier, weather, airspace and late-aircraft factors.",
                       "Select a country first, compare its airlines, then choose one airline to isolate its profile.",
                       "Data: portfolio simulation for demonstration and scenario analysis."),
            html.Div([dcc.Graph(id="chart-airline-bar",config=g,style={"height":"340px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([dcc.Graph(id="chart-cause-stack",config=g,style={"height":"320px"})],style=CARD_STYLE),
        ])

    def page_routes(self):
        g={"displayModeBar":False}
        return html.Div([
            self.intro("ROUTES & CONNECTIVITY","Find busy and delay-sensitive connections",
                       "Combines a route heatmap, volume-versus-delay comparison and a direct Gulf airport path explorer.",
                       "Use country, gateway and airline filters to reveal where simulated operational pressure is concentrated.",
                       "Data: simulated Saudi/UAE origin-destination operations."),
            html.Div([dcc.Graph(id="chart-heatmap",config=g,style={"height":"480px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            html.Div([dcc.Graph(id="chart-bubble",config=g,style={"height":"420px"})],style={**CARD_STYLE,"marginBottom":"12px"}),
            self.page_graph(),
        ])

    def page_trends(self):
        g={"displayModeBar":False}
        return html.Div([
            self.intro("TRENDS","Explore seasonality and changing delay pressure",
                       "Shows how simulated delayed-flight volume and average delay change throughout the year, plus the most affected routes.",
                       "Adjust the month range and airline filter to compare seasonal patterns and carrier exposure.",
                       "Data: portfolio simulation; use patterns as analytical examples, not forecasts."),
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
            self.intro("AIRPORTS","Compare gateway scale and delay exposure",
                       "Maps supported Saudi and UAE gateways; marker size represents simulated flight volume and color represents delay rate.",
                       "Switch country or choose an airline to see which origin airports matter most for that operating context.",
                       "Data: simulated operations; airport locations are real."),
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

    def page_ml(self, status, charts):
        if not status.get("available"):
            return html.Div([
                self.intro(
                    "ML INTELLIGENCE", "Model governance and evaluation",
                    "Shows which delay model is serving predictions, how it compares with the baseline and whether its probabilities are calibrated.",
                    "Start the prediction API or deploy the API container to load the model artifact.",
                    "No heuristic is presented as a trained model.",
                ),
                html.Div([
                    html.Div("MODEL UNAVAILABLE",style={"fontSize":"11px","fontWeight":"700","color":AMBER,"letterSpacing":"1.4px"}),
                    html.Div(status.get("reason","Model artifact could not be loaded."),style={"fontSize":"13px","color":TEXT,"marginTop":"8px"}),
                ],style={**CARD_STYLE,"borderLeft":f"3px solid {AMBER}"}),
            ])

        metrics = status.get("metrics", {})
        champion_metrics = metrics.get(status.get("champion"), {})
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
        deployment_steps = [
            ("1", "Offline training", "2023 fit · 2024 calibration · 2025 evaluation"),
            ("2", "Versioned artifact", status.get("version", "Unknown version")),
            ("3", "FastAPI inference", "Artifact loaded once and retained in API memory"),
            ("4", "Dashboard consumer", "Prediction Lab calls POST /predict/gulf"),
        ]
        return html.Div([
            self.intro(
                "ML INTELLIGENCE", "Delay model control room",
                "Separates model quality, explainability and deployment health from operational analytics and scenario inputs.",
                "Review the champion against its baseline, inspect probability calibration and feature importance, then use Prediction Lab for a scenario.",
                status.get("limitations","Portfolio simulation; not an official airline forecast."),
            ),
            html.Div([
                summary_card("CHAMPION", "CatBoost", status.get("algorithm",""), CYAN),
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
                    html.Div("DEPLOYMENT STATUS",style={"fontSize":"10px","fontWeight":"700","color":GREEN,"letterSpacing":"1.4px","marginBottom":"10px"}),
                    html.Div("● MODEL LOADED",style={"fontSize":"13px","fontWeight":"700","color":GREEN}),
                    html.Div("Serving through FastAPI · dashboard does not deserialize the model",style={"fontSize":"11px","color":MUTED,"marginTop":"8px"}),
                ],style={**CARD_STYLE,"flex":"1","borderLeft":f"3px solid {GREEN}"}),
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

    def page_predict(self):
        fld=lambda lbl,ph,fid,typ="number": html.Div([
            html.Div(lbl,style={"color":MUTED,"fontSize":"11px","marginBottom":"5px"}),
            dcc.Input(id=fid,type=typ,placeholder=ph,debounce=True,style={
                "width":"100%","backgroundColor":SURFACE,"color":TEXT,"border":f"1px solid {BORDER}",
                "borderRadius":"8px","padding":"8px 12px","fontSize":"13px","boxSizing":"border-box"})],
            style={"marginBottom":"12px"})
        return html.Div([
            self.intro("PREDICTION LAB","Test a Gulf delay scenario",
                       "Uses the calibrated CatBoost model served by FastAPI to estimate delay probability from portfolio route, carrier, calendar and weather features.",
                       "Change the route, carrier, departure hour and weather inputs to see how the scenario responds.",
                       "Output: portfolio what-if model; not official airline or airport status."),
            html.Div([
            html.Div("Gulf Delay Prediction Lab",style={"fontSize":"15px","fontWeight":"700","color":TEXT,"marginBottom":"4px"}),
            html.Div("Scenario estimate trained from the portfolio simulation; it is not official airline status.",style={"fontSize":"12px","color":MUTED,"marginBottom":"20px"}),
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
                html.Div([fld("Departure hour (0–23)","18","pred-hour"),fld("Wind (km/h)","25","pred-wind"),
                          fld("Precipitation (mm)","0","pred-precip"),fld("Cloud cover (%)","20","pred-cloud")],style={"flex":"1"}),
            ],style={"display":"flex","gap":"24px"}),
            html.Button("Run Scenario Prediction →",id="btn-predict",n_clicks=0,style={
                "backgroundColor":CYAN,"color":BG,"border":"none","borderRadius":"8px",
                "padding":"10px 28px","fontSize":"13px","fontWeight":"700","cursor":"pointer","marginTop":"8px"}),
            html.Div(id="prediction-result",style={"marginTop":"20px"}),
            ],style={**CARD_STYLE,"maxWidth":"780px"}),
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
            c=GREEN; l="● HYBRID GULF DATA"
            return html.Div(l,style={"fontSize":"10px","fontWeight":"700","color":c,"border":f"1px solid {c}","borderRadius":"20px","padding":"3px 10px"})

        app.clientside_callback(
            "function(a,b,c,d,e,f,g,h,i,cur){const t=dash_clientside.callback_context.triggered;if(!t||!t.length)return cur;return t[0].prop_id.split('.')[0].replace('nav-','');}",
            Output("page","data"),
            [Input(f"nav-{p}","n_clicks") for p in ["live","overview","airlines","map","routes","trends","risk","ml","predict"]],
            State("page","data"),prevent_initial_call=True)

        @app.callback(
            Output("airline-filter-section","style"),
            Output("analytics-filter-section","style"),
            Input("page","data"),
        )
        def contextual_sidebar(page):
            analytics_pages={"overview","airlines","map","routes","trends"}
            visible={} if page in analytics_pages else {"display":"none"}
            return visible, visible

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

        @app.callback(Output("page-content","children"),Output("page-header","children"),
                      Input("page","data"),*ins)
        def render(page,country,airport,a,year,m,d):
            df=_f(country,airport,a,year,m,d)
            titles={"overview":"Historical Operations · Portfolio Simulation","airlines":"Airline Performance","routes":"Routes & Connectivity",
                    "trends":"Monthly Trends","risk":"◈ Gulf Flight Risk Analyzer","map":"🗺 Saudi & UAE Airport Map",
                    "live":"◉ Live Gulf Airspace","ml":"◆ ML Intelligence","predict":"⌁ Prediction Lab"}
            pages={"live":lb.page_live,"overview":lb.page_overview,"airlines":lb.page_airlines,
                   "routes":lb.page_routes,"trends":lb.page_trends,"map":lb.page_map,
                   "predict":lb.page_predict}
            if page == "risk":
                content = lb.page_risk(df)
            elif page == "ml":
                content = lb.page_ml(get_ml_status(), charts)
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

        @app.callback(
            Output("gulf-focus", "children"),
            Input("filter-gulf-country", "value"),
            Input("filter-gulf-airport", "value"),
        )
        def gulf_focus(country, airport):
            if country == "ALL":
                airport_name = "All Saudi and UAE gateways"
                if airport != "ALL":
                    for market in GULF_COUNTRIES.values():
                        if airport in market["airports"]:
                            airport_name = market["airports"][airport]
                            break
                return html.Div([
                    html.Div([
                        html.Span("🌍  Saudi Arabia + UAE",style={"fontSize":"14px","fontWeight":"700","color":TEXT}),
                        html.Span(" · ",style={"color":MUTED}),
                        html.Span(f"{airport if airport != 'ALL' else 'All gateways'} · {airport_name}",style={"fontSize":"12px","color":CYAN}),
                    ]),
                    html.Div("Combined Gulf portfolio lens across both countries",style={"fontSize":"11px","color":MUTED,"marginTop":"5px"}),
                ],style={**CARD_STYLE,"padding":"12px 16px","borderLeft":f"3px solid {GREEN}"})
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
                    html.Span(f"{airport if airport != 'ALL' else 'All gateways'} · {airport_name}",style={"fontSize":"12px","color":CYAN}),
                ]),
                html.Div(f"{market['focus']} · shared country, gateway and airline context for every operations view",style={"fontSize":"11px","color":MUTED,"marginTop":"5px"}),
            ],style={**CARD_STYLE,"padding":"12px 16px","borderLeft":f"3px solid {GREEN}"})

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
            Output("chart-live-map","figure"),Output("live-table","data"),
            Output("live-status","children"),Output("live-status","style"),
            Output("live-count","children"),Output("live-updated","children"),
            Output("live-weather","children"),
            Input("tick","n_intervals"),Input("filter-gulf-country","value"),
            Input("filter-gulf-airport","value"),
        )
        def live_airspace(_, country, airport):
            payload=get_live_flights(country,airport)
            rows=payload.get("data",[])
            is_live=bool(payload.get("is_live"))
            color=GREEN if is_live else AMBER
            status="● LIVE · OPENSKY" if is_live else "● LIVE FEED UNAVAILABLE"
            updated=payload.get("last_updated")
            if updated:
                try:
                    updated=pd.to_datetime(updated,utc=True).strftime("Updated %H:%M:%S UTC")
                except Exception:
                    updated=f"Updated {updated}"
            else:
                updated="No current snapshot"
            source=payload.get("source","OpenSky Network")
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
                "callsign","origin","destination","current_area","current_position","nearest_airport",
                "distance_to_airport_km","altitude_ft","speed_kmh","heading",
                "registration_country","route_source",
            ]} for row in rows]
            return (
                charts.live_aircraft_map(rows,country,airport),table_rows,status,
                {"fontSize":"11px","fontWeight":"700","letterSpacing":"1.5px","color":color},
                f"{len(rows)} aircraft",updated,weather_card,
            )

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
            try:
                response=requests.post(f"{API_BASE_URL}/predict/gulf",json=payload,timeout=12)
                response.raise_for_status()
                prediction=response.json()
            except requests.RequestException as exc:
                return html.Div([
                    html.Div("MODEL SERVICE UNAVAILABLE",style={"fontSize":"11px","fontWeight":"700","color":AMBER,"letterSpacing":"1.4px"}),
                    html.Div(str(exc),style={"fontSize":"11px","color":MUTED,"marginTop":"8px"}),
                ],style={**CARD_STYLE,"borderLeft":f"3px solid {AMBER}"})
            probability=float(prediction["delay_probability"])
            color=GREEN if probability<0.30 else AMBER if probability<0.60 else RED
            label=prediction["risk_band"]
            return html.Div([
                html.Div(f"{label} DELAY RISK",style={"fontSize":"11px","fontWeight":"700","letterSpacing":"1.4px","color":color}),
                html.Div(f"{probability*100:.1f}%",style={"fontSize":"38px","fontWeight":"700","color":color,"margin":"5px 0"}),
                html.Div(f"{airline} · {origin} → {dest} · {flight_date} at {int(hour):02d}:00",style={"fontSize":"12px","color":TEXT}),
                html.Div(f"{prediction['algorithm']} · {prediction['model_version']}",style={"fontSize":"10px","color":CYAN,"marginTop":"8px"}),
                html.Div(prediction["limitations"],style={"fontSize":"10px","color":MUTED,"marginTop":"5px"}),
            ],style={**CARD_STYLE,"borderLeft":f"3px solid {color}"})



    def run(self,debug=False,port=8050):
        self.app.run(debug=debug,host="0.0.0.0",port=port)

if __name__=="__main__":
    App().run(debug=False,port=8050)
