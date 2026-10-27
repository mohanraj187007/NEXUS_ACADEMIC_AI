"""
Risk Analytics Hub View
Deep-dive into the 7-Factor Multidimensional Risk Engine, cohort score distributions,
real Machine Learning classification model evaluation (with train/test split & genuine metrics),
and filterable cohort risk registry.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from analytics.risk_engine import calculate_cohort_risk_registry, calculate_student_risk
from analytics.ml_risk_model import train_and_evaluate_risk_model, predict_student_risk_ml
from database.database import get_setting
from utils.helpers import render_kpi_card, get_risk_badge, format_plotly_theme, render_empty_state


def render_risk_analytics(df: pd.DataFrame):
    """Renders the multidimensional risk analytics and ML validation page."""
    st.markdown('<div class="main-header-title">🎯 Multidimensional Risk & ML Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-header-subtitle">Explainable 0–100 composite risk scoring powered by 7 behavioral factors and verified holdout Machine Learning evaluation</div>', unsafe_allow_html=True)

    if df.empty:
        render_empty_state("No attendance records available to evaluate risk scoring.")
        return

    tab_rule, tab_ml = st.tabs([
        "🎯 7-Factor Rule-Based Scoring Engine",
        "🧠 Predictive ML Model (Holdout Evaluation & Metrics)"
    ])

    # TAB 1: 7-FACTOR ENGINE
    with tab_rule:
        risk_df = calculate_cohort_risk_registry(df)
        if risk_df.empty:
            st.info("No student risk profiles generated.")
            return

        # Top KPI summary
        total = len(risk_df)
        crit_n = (risk_df["risk_level"] == "CRITICAL").sum()
        high_n = (risk_df["risk_level"] == "HIGH").sum()
        med_n = (risk_df["risk_level"] == "MEDIUM").sum()
        low_n = (risk_df["risk_level"] == "LOW").sum()
        avg_score = risk_df["risk_score"].mean()

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            render_kpi_card("Mean Cohort Risk", f"{avg_score:.1f}/100", "Composite average", border_color="#818CF8")
        with c2:
            render_kpi_card("Critical Risk (81-100)", f"{crit_n}", f"{(crit_n/total*100):.1f}% of cohort", border_color="#991B1B")
        with c3:
            render_kpi_card("High Risk (61-80)", f"{high_n}", f"{(high_n/total*100):.1f}% of cohort", border_color="#EF4444")
        with c4:
            render_kpi_card("Medium Risk (31-60)", f"{med_n}", f"{(med_n/total*100):.1f}% of cohort", border_color="#F59E0B")
        with c5:
            render_kpi_card("Low Risk (0-30)", f"{low_n}", f"{(low_n/total*100):.1f}% of cohort", border_color="#10B981")

        st.markdown("<br>", unsafe_allow_html=True)

        # Visual Analytics: Score Distribution Histogram & Factor Weight Architecture
        c_hist, c_model = st.columns([1.2, 1])

        with c_hist:
            st.subheader("📊 Cohort Risk Score Distribution")
            fig_hist = px.histogram(
                risk_df,
                x="risk_score",
                nbins=20,
                color="risk_level",
                color_discrete_map={
                    "LOW": "#10B981",
                    "MEDIUM": "#F59E0B",
                    "HIGH": "#EF4444",
                    "CRITICAL": "#991B1B"
                },
                marginal="box"
            )
            fig_hist.update_xaxes(title="Risk Score (0–100)", range=[0, 100])
            fig_hist.update_yaxes(title="Student Count")
            format_plotly_theme(fig_hist, height=330)
            st.plotly_chart(fig_hist, use_container_width=True)

        with c_model:
            st.subheader("⚙️ 7-Factor Model Architecture")
            weights_df = pd.DataFrame({
                "Dimension": [
                    "Attendance % Deficit",
                    "Recent Trend Velocity",
                    "Absence Streak Impact",
                    "Subject Vulnerability",
                    "Volatility & Variance",
                    "Recovery Difficulty",
                    "Class Benchmark Deficit"
                ],
                "Max Points": [30, 20, 15, 10, 10, 10, 5],
                "Category": ["Direct", "Velocity", "Streak", "Subject", "Pattern", "Mathematical", "Benchmark"]
            })
            fig_weights = px.bar(
                weights_df,
                x="Max Points",
                y="Dimension",
                orientation="h",
                color="Max Points",
                color_continuous_scale="Viridis",
                text="Max Points"
            )
            fig_weights.update_traces(texttemplate='%{text} pts', textposition='outside')
            fig_weights.update_xaxes(range=[0, 35])
            format_plotly_theme(fig_weights, height=330)
            fig_weights.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_weights, use_container_width=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Comprehensive Risk Registry with Interactive Filtering
        st.subheader("📋 Cohort Risk Score Registry")
        
        col_f1, col_f2 = st.columns([1, 2])
        with col_f1:
            filter_risk = st.selectbox("Filter by Risk Category:", ["ALL", "CRITICAL", "HIGH", "MEDIUM", "LOW"], key="risk_cat_sel")
        with col_f2:
            search_query = st.text_input("Search student name or register number:", key="risk_search_input")

        filtered_reg = risk_df.copy()
        if filter_risk != "ALL":
            filtered_reg = filtered_reg[filtered_reg["risk_level"] == filter_risk]
        if search_query:
            q = search_query.strip().lower()
            filtered_reg = filtered_reg[
                filtered_reg["name"].str.lower().str.contains(q) |
                filtered_reg["register_number"].str.lower().str.contains(q)
            ]

        st.markdown(f"**Showing {len(filtered_reg)} of {len(risk_df)} students**")
        
        display_reg = filtered_reg[[
            "register_number", "name", "department", "attendance_pct", "risk_score", "risk_level",
            "trend", "current_streak", "primary_subject", "required_consecutive", "recommended_action"
        ]].copy()
        display_reg.columns = [
            "Reg No", "Student Name", "Department", "Att %", "Score", "Tier",
            "Trend", "Streak", "Worst Subject", "Req Classes (75%)", "Recommended Action"
        ]

        st.dataframe(
            display_reg.style.map(
                lambda v: "color: #EF4444; font-weight: bold;" if v in ["CRITICAL", "HIGH"] else ("color: #F59E0B; font-weight: bold;" if v == "MEDIUM" else "color: #10B981;"),
                subset=["Tier"]
            ),
            use_container_width=True,
            height=360
        )

    # TAB 2: MACHINE LEARNING EVALUATION
    with tab_ml:
        st.subheader("🧠 Machine Learning Model Training & Holdout Test Metrics")
        st.markdown("""
        Evaluates a **RandomForest Classifier** on a 75/25 holdout test split with `class_weight='balanced'` 
        to accurately classify at-risk students while accounting for class imbalance.
        <b>No fabricated metrics:</b> All scores below reflect genuine test-set evaluations.
        """, unsafe_allow_html=True)

        thresh = float(get_setting("mandatory_attendance_pct", 75.0))
        ml_eval = train_and_evaluate_risk_model(df, threshold=thresh)

        if ml_eval["status"] != "TRAINED_SUCCESS":
            st.warning(f"⚠️ {ml_eval.get('message', 'ML Model requires sufficient distinct student profiles.')}")
            st.info("The system continues operating with the 7-factor explainable rule engine until sufficient student history is accumulated.")
        else:
            # Display Real Test Set Metrics
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                render_kpi_card("Test Precision", f"{ml_eval['precision']:.3f}", "Positive Predictive Value", border_color="#38BDF8")
            with m2:
                render_kpi_card("Test Recall (Sensitivity)", f"{ml_eval['recall']:.3f}", "True Positive Rate", border_color="#10B981")
            with m3:
                render_kpi_card("Test F1-Score", f"{ml_eval['f1_score']:.3f}", "Harmonic Precision-Recall", border_color="#F59E0B")
            with m4:
                render_kpi_card("Test ROC-AUC", f"{ml_eval['roc_auc']:.3f}", "Area Under ROC Curve", border_color="#A855F7")

            col_split1, col_split2 = st.columns(2)
            with col_split1:
                st.markdown(f"""
                <div class="analysis-card">
                    <b style="color: #38BDF8;">Dataset Validation Split:</b><br>
                    &bull; <b>Total Cohort Samples:</b> {ml_eval['total_cohort_samples']} students<br>
                    &bull; <b>Training Split (75%):</b> {ml_eval['train_samples']} students<br>
                    &bull; <b>Holdout Test Split (25%):</b> {ml_eval['test_samples']} students<br>
                    &bull; <b>Class Distribution:</b> Compliant: {ml_eval['class_distribution'].get(0, 0)} | At-Risk: {ml_eval['class_distribution'].get(1, 0)}
                </div>
                """, unsafe_allow_html=True)

            with col_split2:
                st.markdown("##### 🔍 Test Confusion Matrix")
                cm = ml_eval["confusion_matrix"]
                if len(cm) == 2:
                    cm_df = pd.DataFrame(
                        cm,
                        index=["Actual Compliant", "Actual At-Risk"],
                        columns=["Pred Compliant", "Pred At-Risk"]
                    )
                    st.dataframe(cm_df, use_container_width=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Feature Importance
            st.subheader("📊 Feature Importance Breakdown (MDI)")
            imp_df = pd.DataFrame(ml_eval["feature_importances"])
            fig_imp = px.bar(
                imp_df,
                x="importance",
                y="feature",
                orientation="h",
                color="importance",
                color_continuous_scale="Purples",
                text="importance"
            )
            fig_imp.update_traces(texttemplate='%{text:.3f}', textposition='outside')
            format_plotly_theme(fig_imp, height=320)
            fig_imp.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig_imp, use_container_width=True)
