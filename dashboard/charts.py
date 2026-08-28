"""
charts.py — DST Airlines · Plotly Chart Factory (OOP)
Professional dark theme · Fixed legend positions · Aviation-grade palette
"""
from math import cos, radians, sin

import plotly.graph_objects as go
import pandas as pd
from plotly.colors import sample_colorscale

from data import DELAY_CAUSES

# ── Professional Aviation Palette ──────────────────────────────────────────
BG       = "#0a0e1a"
CARD     = "#0f1523"
SURFACE  = "#161d2e"
BORDER   = "#1e2a3a"
CYAN     = "#00d4ff"
CYAN_DIM = "rgba(0,212,255,0.12)"
BLUE     = "#4a9eff"
PURPLE   = "#8b5cf6"
GREEN    = "#10b981"
AMBER    = "#f59e0b"
TEXT     = "#f1f5f9"
MUTED    = "#64748b"
GRID     = "#1e2a3a"
CAT_COLORS = [CYAN, BLUE, PURPLE, GREEN, AMBER]


def _offset_geo_point(latitude: float, longitude: float, east_km: float, north_km: float):
    """Move a map point by a small local east/north offset."""
    latitude_delta = north_km / 110.574
    longitude_scale = max(0.2, cos(radians(latitude)))
    longitude_delta = east_km / (111.320 * longitude_scale)
    return latitude + latitude_delta, longitude + longitude_delta


def _aircraft_polygon(latitude: float, longitude: float, heading: float, scale_km: float = 55):
    """Return a recognizable aircraft silhouette rotated to a compass heading."""
    outline = [
        (0.00, 1.00), (0.12, 0.58), (0.14, 0.16),
        (0.68, -0.14), (0.68, -0.30), (0.14, -0.20),
        (0.11, -0.64), (0.36, -0.86), (0.34, -0.98),
        (0.00, -0.84), (-0.34, -0.98), (-0.36, -0.86),
        (-0.11, -0.64), (-0.14, -0.20), (-0.68, -0.30),
        (-0.68, -0.14), (-0.14, 0.16), (-0.12, 0.58),
        (0.00, 1.00),
    ]
    angle = radians(float(heading or 0))
    points = []
    for east, north in outline:
        east *= scale_km
        north *= scale_km
        rotated_east = east * cos(angle) + north * sin(angle)
        rotated_north = -east * sin(angle) + north * cos(angle)
        points.append(
            _offset_geo_point(latitude, longitude, rotated_east, rotated_north)
        )
    return points

def _base(title: str = "", margin_t: int = 50) -> dict:
    return dict(
        paper_bgcolor=CARD,
        plot_bgcolor=CARD,
        font=dict(family="'DM Sans', 'Inter', sans-serif", color=TEXT, size=12),
        margin=dict(l=48, r=24, t=margin_t, b=60),
        title=dict(
            text=title,
            font=dict(size=14, color=TEXT),
            x=0, xanchor="left", pad=dict(l=4),
            y=0.97, yanchor="top",
        ),
        xaxis=dict(gridcolor=GRID, zerolinecolor=GRID,
                   tickfont=dict(color=MUTED, size=11), linecolor=BORDER),
        yaxis=dict(gridcolor=GRID, zerolinecolor=GRID,
                   tickfont=dict(color=MUTED, size=11), linecolor=BORDER),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=MUTED, size=11),
            orientation="h",
            x=0, y=-0.22,
            xanchor="left", yanchor="top",
        ),
        hoverlabel=dict(
            bgcolor=SURFACE, bordercolor=BORDER,
            font=dict(color=TEXT, size=12),
        ),
    )


class ChartFactory:

    def monthly_trend(self, df: pd.DataFrame) -> go.Figure:
        MN = ["Jan","Feb","Mar","Apr","May","Jun",
              "Jul","Aug","Sep","Oct","Nov","Dec"]
        years = sorted(df["Year"].dropna().astype(int).unique()) if "Year" in df.columns else []
        year_scope = str(years[0]) if len(years) == 1 else "Selected period"
        monthly = (df.groupby("Month")
                     .agg(avg_delay=("DepDelay","mean"), delayed_count=("Delayed","sum"))
                     .reset_index())
        monthly["MonthName"] = monthly["Month"].apply(lambda m: MN[m-1])
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=monthly["MonthName"], y=monthly["delayed_count"],
            yaxis="y2", name="Delayed Flights",
            marker=dict(color="rgba(74,158,255,0.12)",
                        line=dict(color="rgba(74,158,255,0.3)", width=1)),
            hovertemplate="<b>%{x}</b><br>Delayed: <b>%{y}</b><extra></extra>",
        ))
        fig.add_trace(go.Scatter(
            x=monthly["MonthName"], y=monthly["avg_delay"].round(1),
            mode="lines+markers", name="Avg Delay (min)",
            line=dict(color=CYAN, width=2.5, shape="spline"),
            marker=dict(size=8, color=CARD, line=dict(color=CYAN, width=2.5)),
            fill="tozeroy", fillcolor="rgba(0,212,255,0.06)",
            hovertemplate="<b>%{x}</b><br>Avg delay: <b>%{y} min</b><extra></extra>",
        ))
        layout = _base(f"Monthly Delay Performance · {year_scope} simulated history")
        layout["yaxis2"] = dict(overlaying="y", side="right", gridcolor=GRID,
                                tickfont=dict(color=MUTED, size=11),
                                showgrid=False, linecolor=BORDER)
        fig.update_layout(**layout)
        return fig

    def airline_delay_bar(self, df: pd.DataFrame) -> go.Figure:
        grp = (df.groupby("Operating_Airline")
                 .agg(delay_rate=("Delayed","mean"), total=("Delayed","count"))
                 .reset_index().sort_values("delay_rate", ascending=True))
        grp["pct"] = (grp["delay_rate"] * 100).round(1)
        norm = (grp["pct"] - grp["pct"].min()) / (grp["pct"].max() - grp["pct"].min() + 0.01)
        colors = [f"rgba({int(16+r*139)},{int(185-r*30)},{int(129+r*67)},0.85)" for r in norm]
        fig = go.Figure(go.Bar(
            y=grp["Operating_Airline"], x=grp["pct"], orientation="h",
            marker=dict(color=colors, line=dict(color="rgba(255,255,255,0.05)", width=1)),
            text=grp["pct"].astype(str) + "%",
            textposition="outside", textfont=dict(color=TEXT, size=11),
            hovertemplate="<b>%{y}</b><br>Delay rate: <b>%{x:.1f}%</b><br>Flights: %{customdata}<extra></extra>",
            customdata=grp["total"],
        ))
        fig.update_layout(**_base("Delay Rate by Airline"))
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title_text="Delay Rate (%)", title_font=dict(color=MUTED, size=11),
                         range=[0, grp["pct"].max() * 1.25])
        return fig

    def delay_cause_stack(self, df: pd.DataFrame) -> go.Figure:
        grp = df.groupby("Operating_Airline")[DELAY_CAUSES].mean().reset_index()
        labels = ["Carrier","Weather","NAS","Security","Late Aircraft"]
        fig = go.Figure()
        for cause, label, color in zip(DELAY_CAUSES, labels, CAT_COLORS):
            fig.add_trace(go.Bar(
                name=label, x=grp["Operating_Airline"], y=grp[cause].round(1),
                marker=dict(color=color, opacity=0.85,
                            line=dict(color="rgba(255,255,255,0.04)", width=0.5)),
                hovertemplate=f"<b>%{{x}}</b><br>{label}: <b>%{{y:.1f}} min</b><extra></extra>",
            ))
        layout = _base("Delay Causes by Airline (avg min)")
        layout["barmode"] = "stack"
        fig.update_layout(**layout)
        fig.update_xaxes(tickangle=-20)
        return fig

    def route_heatmap(self, df: pd.DataFrame) -> go.Figure:
        pivot = (df.pivot_table(index="Origin", columns="Dest",
                                values="DepDelay", aggfunc="mean")
                   .fillna(0).round(1))
        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
            colorscale=[[0,"#0a0e1a"],[0.3,"#0f2a4a"],[0.6,"#1a5fa0"],
                        [0.8,CYAN],[1.0,PURPLE]],
            hoverongaps=False,
            hovertemplate="<b>%{y} → %{x}</b><br>Avg delay: <b>%{z:.1f} min</b><extra></extra>",
            showscale=True,
            colorbar=dict(tickfont=dict(color=MUTED, size=10), outlinewidth=0,
                          title=dict(text="min", font=dict(color=MUTED, size=10))),
        ))
        fig.update_layout(**_base("Avg Departure Delay by Route (min)"))
        fig.update_layout(showlegend=False)
        return fig

    def dow_delay(self, df: pd.DataFrame) -> go.Figure:
        order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        grp = (df.groupby("DayOfWeek")["DepDelay"].mean().reindex(order).reset_index())
        max_v = grp["DepDelay"].max()
        colors = [AMBER if v == max_v else BLUE for v in grp["DepDelay"]]
        fig = go.Figure(go.Bar(
            x=grp["DayOfWeek"], y=grp["DepDelay"].round(1),
            marker=dict(color=colors, opacity=0.85,
                        line=dict(color="rgba(255,255,255,0.04)", width=0.5)),
            text=grp["DepDelay"].round(1), textposition="outside",
            textfont=dict(color=TEXT, size=11),
            hovertemplate="<b>%{x}</b><br>Avg delay: <b>%{y:.1f} min</b><extra></extra>",
        ))
        fig.update_layout(**_base("Avg Delay by Day of Week"))
        fig.update_layout(showlegend=False)
        fig.update_xaxes(tickangle=-15)
        return fig

    def delay_histogram(self, df: pd.DataFrame) -> go.Figure:
        delayed = df[df["DepDelay"] > 0]["DepDelay"].clip(upper=180)
        mean_val = delayed.mean()
        fig = go.Figure(go.Histogram(
            x=delayed, nbinsx=36,
            marker=dict(color=CYAN_DIM, line=dict(color=CYAN, width=0.8)),
            hovertemplate="Delay: <b>%{x} min</b><br>Flights: <b>%{y}</b><extra></extra>",
        ))
        fig.add_vline(x=mean_val, line_width=1.5, line_dash="dash", line_color=AMBER,
                      annotation_text=f"Mean: {mean_val:.0f} min",
                      annotation_font_color=AMBER, annotation_font_size=11,
                      annotation_position="top right")
        fig.update_layout(**_base("Departure Delay Distribution"))
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title_text="Delay (minutes)", title_font=dict(color=MUTED, size=11))
        fig.update_yaxes(title_text="Number of Flights", title_font=dict(color=MUTED, size=11))
        return fig

    def top_routes(self, df: pd.DataFrame) -> go.Figure:
        grp = (df.groupby(["Origin","Dest"])
                 .agg(avg_delay=("DepDelay","mean"), total=("DepDelay","count"))
                 .reset_index())
        grp = grp[grp["total"] >= 5].nlargest(10, "avg_delay")
        grp["route"] = grp["Origin"] + " → " + grp["Dest"]
        fig = go.Figure(go.Bar(
            y=grp["route"], x=grp["avg_delay"].round(1), orientation="h",
            marker=dict(color=grp["avg_delay"],
                        colorscale=[[0,"#1a5fa0"],[0.5,CYAN],[1,PURPLE]],
                        showscale=False,
                        line=dict(color="rgba(255,255,255,0.04)", width=0.5)),
            text=grp["avg_delay"].round(1).astype(str) + " min",
            textposition="outside", textfont=dict(color=TEXT, size=11),
            hovertemplate="<b>%{y}</b><br>Avg delay: <b>%{x:.1f} min</b><extra></extra>",
        ))
        fig.update_layout(**_base("Top 10 Most Delayed Routes"))
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title_text="Avg Delay (min)", title_font=dict(color=MUTED, size=11))
        return fig

    def route_heatmap_top(self, df: pd.DataFrame) -> go.Figure:
        """Heatmap limited to top 20 busiest airports for readability."""
        # Find top 20 airports by flight count
        top_origins = df["Origin"].value_counts().head(20).index.tolist()
        top_dests   = df["Dest"].value_counts().head(20).index.tolist()
        top_airports = list(set(top_origins + top_dests))[:20]

        sub = df[df["Origin"].isin(top_airports) & df["Dest"].isin(top_airports)]
        pivot = (sub.pivot_table(index="Origin", columns="Dest",
                                 values="DepDelay", aggfunc="mean")
                    .round(1))

        fig = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[
                [0.0, "#0a0e1a"], [0.2, "#0f2a4a"],
                [0.5, "#1a5fa0"], [0.8, CYAN],  [1.0, PURPLE],
            ],
            hoverongaps=False,
            hovertemplate="<b>%{y} → %{x}</b><br>Avg delay: <b>%{z:.1f} min</b><extra></extra>",
            showscale=True,
            zmin=0,
            colorbar=dict(
                tickfont=dict(color=MUTED, size=10),
                outlinewidth=0,
                title=dict(text="min", font=dict(color=MUTED, size=10)),
                thickness=12,
            ),
            xgap=2, ygap=2,
        ))
        layout = _base("Route Delay Heatmap — Top 20 Busiest Airports", margin_t=50)
        layout["margin"] = dict(l=60, r=80, t=50, b=80)
        fig.update_layout(**layout)
        fig.update_layout(showlegend=False)
        fig.update_xaxes(tickangle=-45, tickfont=dict(size=10, color=MUTED))
        fig.update_yaxes(tickfont=dict(size=10, color=MUTED))
        return fig

    def top_routes_bubble(self, df: pd.DataFrame) -> go.Figure:
        """Scatter: x=avg delay, y=total flights, size=delay rate — top 30 routes."""
        grp = (df.groupby(["Origin", "Dest"])
                 .agg(
                     avg_delay=("DepDelay", "mean"),
                     total=("DepDelay", "count"),
                     delayed=("Delayed", "sum"),
                 ).reset_index())
        grp = grp[grp["total"] >= 20].copy()
        grp["delay_rate"] = (grp["delayed"] / grp["total"] * 100).round(1)
        grp["route"] = grp["Origin"] + " → " + grp["Dest"]
        grp = grp.nlargest(30, "total")
        grp["avg_delay"] = grp["avg_delay"].round(1)

        fig = go.Figure(go.Scatter(
            x=grp["avg_delay"],
            y=grp["total"],
            mode="markers+text",
            marker=dict(
                size=grp["delay_rate"] * 1.2,
                color=grp["avg_delay"],
                colorscale=[[0, BLUE], [0.5, CYAN], [1, PURPLE]],
                showscale=True,
                opacity=0.8,
                line=dict(color="rgba(255,255,255,0.1)", width=1),
                colorbar=dict(
                    title=dict(text="Avg delay (min)", font=dict(color=MUTED, size=10)),
                    tickfont=dict(color=MUTED, size=9),
                    outlinewidth=0, thickness=10,
                ),
            ),
            text=grp["route"],
            textposition="top center",
            textfont=dict(size=9, color=MUTED),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Avg delay: <b>%{x:.1f} min</b><br>"
                "Total flights: <b>%{y:,}</b><br>"
                "Delay rate: <b>%{customdata:.1f}%</b>"
                "<extra></extra>"
            ),
            customdata=grp["delay_rate"],
        ))
        layout = _base("Busiest Routes — Delay vs Volume (bubble size = delay rate %)", margin_t=50)
        fig.update_layout(**layout)
        fig.update_layout(showlegend=False)
        fig.update_xaxes(title_text="Avg Departure Delay (min)",
                         title_font=dict(color=MUTED, size=11))
        fig.update_yaxes(title_text="Total Flights",
                         title_font=dict(color=MUTED, size=11))
        return fig

    def airport_map(self, df: pd.DataFrame) -> go.Figure:
        """Interactive Gulf airport map — bubble size = flights, color = delay rate."""
        from weather import AIRPORT_COORDS

        grp = (df.groupby("Origin")
                 .agg(total=("DepDelay","count"),
                      avg_delay=("DepDelay","mean"),
                      delayed=("Delayed","sum"))
                 .reset_index())
        grp = grp[grp["total"] >= 5].copy()
        grp["delay_rate"] = (grp["delayed"] / grp["total"] * 100).round(1)
        grp["avg_delay"]  = grp["avg_delay"].round(1)

        # Add coordinates
        grp["lat"] = grp["Origin"].map(lambda x: AIRPORT_COORDS.get(x, (None,None))[0])
        grp["lon"] = grp["Origin"].map(lambda x: AIRPORT_COORDS.get(x, (None,None))[1])
        grp = grp.dropna(subset=["lat","lon"])

        fig = go.Figure(go.Scattergeo(
            lat=grp["lat"],
            lon=grp["lon"],
            mode="markers",
            marker=dict(
                size=grp["total"] / grp["total"].max() * 40 + 6,
                color=grp["delay_rate"],
                colorscale=[[0, GREEN],[0.4, AMBER],[1, "#ef4444"]],
                showscale=True,
                opacity=0.85,
                line=dict(color="rgba(255,255,255,0.2)", width=0.5),
                colorbar=dict(
                    title=dict(text="Delay %", font=dict(color=MUTED, size=10)),
                    tickfont=dict(color=MUTED, size=9),
                    outlinewidth=0, thickness=10,
                ),
            ),
            text=grp["Origin"],
            customdata=grp[["total","avg_delay","delay_rate"]].values,
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Total flights: <b>%{customdata[0]:,}</b><br>"
                "Avg delay: <b>%{customdata[1]:.1f} min</b><br>"
                "Delay rate: <b>%{customdata[2]:.1f}%</b>"
                "<extra></extra>"
            ),
        ))

        fig.update_layout(
            paper_bgcolor=CARD,
            plot_bgcolor=CARD,
            font=dict(family="DM Sans", color=TEXT),
            margin=dict(l=0, r=0, t=40, b=0),
            title=dict(text="Saudi Arabia & UAE Airport Delay Map — bubble size = flight volume · color = delay rate",
                      font=dict(size=13, color=TEXT), x=0, xanchor="left", pad=dict(l=10)),
            geo=dict(
                scope="world",
                bgcolor=BG,
                landcolor="#0f1a2e",
                subunitcolor=BORDER,
                countrycolor=BORDER,
                showlakes=True,
                lakecolor=BG,
                showcoastlines=True,
                coastlinecolor=BORDER,
                projection_type="natural earth",
                center=dict(lat=24.5, lon=48.5),
                projection_scale=5.2,
            ),
            height=480,
        )
        return fig

    def live_aircraft_map(self, rows: list[dict], country: str, airport: str) -> go.Figure:
        """Map current OpenSky state vectors without implying schedule status."""
        frame = pd.DataFrame(rows)
        fig = go.Figure()
        if not frame.empty:
            frame["label"] = frame["callsign"].fillna(frame["icao24"]).fillna("Unknown")
            frame["altitude_ft"] = pd.to_numeric(frame.get("altitude_ft"), errors="coerce")
            frame["speed_kmh"] = pd.to_numeric(frame.get("speed_kmh"), errors="coerce")
            frame["heading"] = pd.to_numeric(frame.get("heading"), errors="coerce")
            frame["heading_label"] = frame["heading"].apply(
                lambda value: f"{value:.0f}°" if pd.notna(value) else "Not reported"
            )
            altitude_scale = [[0, GREEN], [0.45, CYAN], [1, PURPLE]]

            route_latitudes = []
            route_longitudes = []
            endpoint_latitudes = []
            endpoint_longitudes = []
            endpoint_labels = []
            aircraft_bands = {}
            for _, aircraft in frame.iterrows():
                latitude = float(aircraft["latitude"])
                longitude = float(aircraft["longitude"])
                heading = aircraft["heading"]

                origin_latitude = aircraft.get("origin_latitude")
                origin_longitude = aircraft.get("origin_longitude")
                destination_latitude = aircraft.get("destination_latitude")
                destination_longitude = aircraft.get("destination_longitude")
                has_route_coordinates = all(pd.notna(value) for value in [
                    origin_latitude,
                    origin_longitude,
                    destination_latitude,
                    destination_longitude,
                ])
                if has_route_coordinates:
                    route_latitudes.extend([
                        float(origin_latitude), float(destination_latitude), None,
                    ])
                    route_longitudes.extend([
                        float(origin_longitude), float(destination_longitude), None,
                    ])
                    endpoint_latitudes.extend([
                        float(origin_latitude), float(destination_latitude),
                    ])
                    endpoint_longitudes.extend([
                        float(origin_longitude), float(destination_longitude),
                    ])
                    endpoint_labels.extend([
                        f"Origin · {aircraft.get('origin', 'Unknown')}",
                        f"Destination · {aircraft.get('destination', 'Unknown')}",
                    ])

                altitude = aircraft["altitude_ft"]
                altitude_fraction = 0 if pd.isna(altitude) else min(max(float(altitude), 0), 45000) / 45000
                band = -1 if pd.isna(altitude) else min(8, int(altitude_fraction * 9))
                aircraft_bands.setdefault(band, {"lat": [], "lon": []})
                polygon = _aircraft_polygon(
                    latitude,
                    longitude,
                    float(heading) if pd.notna(heading) else 0,
                )
                aircraft_bands[band]["lat"].extend([point[0] for point in polygon] + [None])
                aircraft_bands[band]["lon"].extend([point[1] for point in polygon] + [None])

            if route_latitudes:
                fig.add_trace(go.Scattergeo(
                    lat=route_latitudes,
                    lon=route_longitudes,
                    mode="lines",
                    line=dict(color="rgba(0,212,255,0.52)", width=1.6, dash="dot"),
                    name="Matched origin–destination route",
                    hoverinfo="skip",
                ))
                fig.add_trace(go.Scattergeo(
                    lat=endpoint_latitudes,
                    lon=endpoint_longitudes,
                    mode="markers",
                    marker=dict(
                        size=6, symbol="circle-open", color=CYAN,
                        line=dict(color=CYAN, width=1.2),
                    ),
                    customdata=endpoint_labels,
                    hovertemplate="%{customdata}<extra></extra>",
                    showlegend=False,
                ))

            for band, coordinates in sorted(aircraft_bands.items()):
                color = MUTED if band < 0 else sample_colorscale(
                    altitude_scale, [min(1, (band + 0.5) / 9)]
                )[0]
                fig.add_trace(go.Scattergeo(
                    lat=coordinates["lat"],
                    lon=coordinates["lon"],
                    mode="lines",
                    line=dict(color="rgba(255,255,255,0.72)", width=0.7),
                    fill="toself",
                    fillcolor=color,
                    hoverinfo="skip",
                    showlegend=False,
                ))

            altitude_color = frame["altitude_ft"].fillna(0).clip(lower=0, upper=45000)
            fig.add_trace(go.Scattergeo(
                lat=frame["latitude"], lon=frame["longitude"], mode="markers",
                marker={
                    "color": altitude_color,
                    "colorscale": altitude_scale,
                    "cmin": 0,
                    "cmax": 45000,
                    "size": 38,
                    "symbol": "circle",
                    "showscale": True,
                    "opacity": 0.01,
                    "colorbar":dict(
                        title=dict(text="Altitude (ft)", font=dict(color=MUTED, size=10)),
                        tickfont=dict(color=MUTED, size=9), outlinewidth=0, thickness=10,
                    ),
                },
                customdata=frame[["label", "icao24", "altitude_ft", "speed_kmh", "heading_label", "nearest_airport", "distance_to_airport_km"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>ICAO24: %{customdata[1]}<br>"
                    "Altitude: %{customdata[2]:,.0f} ft<br>Speed: %{customdata[3]:,.0f} km/h<br>"
                    "Heading: %{customdata[4]}<br>Nearest gateway: %{customdata[5]} "
                    "(%{customdata[6]:.0f} km)<extra></extra>"
                ),
                showlegend=False,
            ))
        else:
            fig.add_annotation(
                text="No current OpenSky aircraft observations for this filter",
                x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False,
                font=dict(color=MUTED, size=13),
            )

        title_scope = f"{airport} vicinity" if airport and airport != "ALL" else country
        fig.update_layout(
            paper_bgcolor=CARD, plot_bgcolor=CARD,
            font=dict(family="DM Sans", color=TEXT),
            margin=dict(l=0, r=0, t=45, b=0),
            title=dict(
                text=f"Live Gulf aircraft · {title_scope}",
                font=dict(size=13, color=TEXT), x=0, xanchor="left", pad=dict(l=10),
            ),
            legend=dict(
                orientation="h", x=0.01, y=0.99, xanchor="left", yanchor="top",
                bgcolor="rgba(15,21,35,0.78)", bordercolor=BORDER, borderwidth=1,
                font=dict(color=MUTED, size=10),
            ),
            geo=dict(
                scope="world", bgcolor=BG, landcolor="#0f1a2e", countrycolor=BORDER,
                coastlinecolor=BORDER, showcoastlines=True, showlakes=True, lakecolor=BG,
                projection_type="natural earth", center=dict(lat=24.5, lon=48.5),
                projection_scale=5.2,
            ),
            height=520,
        )
        return fig

    def risk_gauge(self, probability: float) -> go.Figure:
        GREEN="#10b981"; AMBER="#f59e0b"; RED="#ef4444"
        if probability < 0.3:   color=GREEN; label="LOW RISK"
        elif probability < 0.6: color=AMBER; label="MEDIUM RISK"
        else:                   color=RED;   label="HIGH RISK"
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(probability*100,1),
            number={"suffix":"%","font":{"color":color,"size":48}},
            gauge={
                "axis":{"range":[0,100],"tickcolor":MUTED},
                "bar":{"color":color},
                "bgcolor":CARD,"bordercolor":BORDER,
                "steps":[
                    {"range":[0,30],"color":"rgba(16,185,129,0.15)"},
                    {"range":[30,60],"color":"rgba(245,158,11,0.15)"},
                    {"range":[60,100],"color":"rgba(239,68,68,0.15)"},
                ],
                "threshold":{"line":{"color":color,"width":3},"thickness":0.75,"value":probability*100},
            },
            title={"text":label,"font":{"color":color,"size":20}},
        ))
        fig.update_layout(paper_bgcolor=CARD,plot_bgcolor=CARD,
                          font=dict(color=TEXT,family="DM Sans"),
                          margin=dict(l=30,r=30,t=60,b=20),height=280)
        return fig
