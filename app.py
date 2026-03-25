import streamlit as st
import pandas as pd
import hashlib

# 1. 页面配置
st.set_page_config(page_title="抓鬼全能自定义版 V19", layout="wide")

# 2. 登录逻辑
if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🔒 财务安全登录")
    pwd = st.text_input("请输入访问密码", type="password")
    if st.button("登录"):
        if pwd == "888":
            st.session_state.auth = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()

# 3. 核心审计逻辑
def run_audit(df, rules):
    try:
        df.columns = [str(c).strip().replace('\n', '').replace('\r', '') for c in df.columns]
        name_map = {
            '个人实际销量': ['个人实际销量', '投注', '个人销量', '实际销量', '销量'],
            '用户名': ['用户名', '会员账号', '账号', '会员', '用户'],
            '投注单数': ['投注单数', '投注次数', '单数', '总注单数', '次数'],
            '个人游戏盈亏': ['个人游戏盈亏', '盈亏', '游戏盈亏', '盈亏金额'],
            'RTP': ['RTP', '返还率', 'rtp', '返奖率']
        }
        actual_cols = {}
        for standard_name, aliases in name_map.items():
            for alias in aliases:
                if alias in df.columns:
                    actual_cols[standard_name] = alias
                    break
        
        required = ['用户名', '个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']
        if not all(r in actual_cols for r in required):
            st.error(f"❌ 列名匹配失败，请检查 Excel 表头。")
            return None

        clean_df = pd.DataFrame()
        clean_df['用户名'] = df[actual_cols['用户名']].astype(str)
        for col in ['个人实际销量', '投注单数', '个人游戏盈亏', 'RTP']:
            clean_df[col] = pd.to_numeric(df[actual_cols[col]], errors='coerce').fillna(0)

        # 聚合数据
        clean_df['返还额'] = clean_df['个人实际销量'] * clean_df['RTP']
        grouped = clean_df.groupby('用户名').agg({
            '个人实际销量': 'sum', '投注单数': 'sum', '个人游戏盈亏': 'sum', '返还额': 'sum'
        }).reset_index()
        grouped['RTP'] = grouped.apply(lambda x: x['返还额'] / x['个人实际销量'] if x['个人实际销量'] > 0 else 0, axis=1)

        # --- 动态筛选逻辑 ---
        def check_user(row):
            v, c, p, r = row['个人实际销量'], row['投注单数'], row['个人游戏盈亏'], row['RTP']
            
            # 只有启用的条件才会参与判断
            is_match = True
            
            if rules['v_on'] and not (rules['v_min'] <= v <= rules['v_max']): is_match = False
            if rules['c_on'] and not (c <= rules['c_limit']): is_match = False
            if rules['p_on'] and not (rules['p_min'] <= p <= rules['p_max']): is_match = False
            if rules['r_on'] and not (rules['r_min'] <= r <= rules['r_max']): is_match = False
            
            return "符合设定条件" if is_match else None

        grouped['原因'] = grouped.apply(check_user, axis=1)
        return grouped[grouped['原因'].notna()].copy()
    except Exception as e:
        st.error(f"审计出错：{e}")
        return None

# 4. 界面显示层
st.title("📊 抓鬼用户 (全参数自由配置版)")

# 侧边栏：规则配置
with st.sidebar:
    st.header("⚙️ 筛选规则设置")
    st.write("勾选即代表开启该项过滤")
    
    # 销量设置
    v_on = st.checkbox("启用销量过滤", value=True)
    v_min = st.number_input("销量最小值", value=1000.0, step=100.0, format="%.2f")
    v_max = st.number_input("销量最大值", value=10000000.0, step=1000.0, format="%.2f")
    
    st.write("---")
    # 单数设置
    c_on = st.checkbox("启用单数过滤", value=True)
    c_limit = st.number_input("投注单数上限 (小于等于)", value=12)
    
    st.write("---")
    # 盈亏设置
    p_on = st.checkbox("启用盈亏过滤", value=False)
    p_min = st.number_input("盈亏最小值", value=-10000000.0, step=100.0, format="%.2f")
    p_max = st.number_input("盈亏最大值", value=10000000.0, step=100.0, format="%.2f")

    st.write("---")
    # RTP 设置
    r_on = st.checkbox("启用 RTP 过滤", value=False)
    r_min = st.number_input("RTP 最小值", value=0.00, step=0.01, format="%.4f")
    r_max = st.number_input("RTP 最大值", value=1.00, step=0.01, format="%.4f")

    # 打包规则
    current_rules = {
        'v_on': v_on, 'v_min': v_min, 'v_max': v_max,
        'c_on': c_on, 'c_limit': c_limit,
        'p_on': p_on, 'p_min': p_min, 'p_max': p_max,
        'r_on': r_on, 'r_min': r_min, 'r_max': r_max
    }

file = st.file_uploader("📂 上传原始数据 (.xlsx)", type=["xlsx"])

if file:
    # 只要规则开关或数值动了，就重新算
    file_bytes = file.getvalue()
    rule_hash = hashlib.md5(str(current_rules).encode()).hexdigest()
    file_hash = hashlib.md5(file_bytes + rule_hash.encode()).hexdigest()
    
    if st.session_state.get("last_hash") != file_hash:
        try:
            raw = pd.read_excel(file)
            result = run_audit(raw, current_rules)
            if result is not None:
                st.session_state.res = result
                st.session_state.read = set()
                st.session_state.last_hash = file_hash
        except Exception as e:
            st.error(f"读取失败：{e}")

    res = st.session_state.get("res")

    if res is not None and not res.empty:
        # 排序
        st.write("---")
        s_col, s_ord = st.columns([2, 1])
        s_by = s_col.selectbox("排序字段", ["个人实际销量", "投注单数", "个人游戏盈亏", "RTP", "用户名"])
        s_dir = s_ord.selectbox("排序方向", ["从大到小", "从小到大"])
        res = res.sort_values(by=s_by, ascending=(s_dir == "从小到大"))

        st.warning(f"🎯 符合条件的异常用户: {len(res)} 个")
        
        # 固定表头
        h_cols = st.columns([1, 2, 2, 2, 1, 2, 2])
        headers = ["确认", "用户名", "筛选结果", "销量", "单数", "盈亏", "RTP"]
        for col, h in zip(h_cols, headers): col.write(f"**{h}**")

        # 滚动区域
        with st.container(height=600):
            for i, row in res.iterrows():
                u = row['用户名']
                is_read = u in st.session_state.read
                r_cols = st.columns([1, 2, 2, 2, 1, 2, 2])
                
                if r_cols[0].checkbox(" ", key=f"chk_{u}_{i}", value=is_read):
                    st.session_state.read.add(u)
                    is_read = True
                else:
                    st.session_state.read.discard(u)
                    is_read = False

                color = "#aaaaaa" if is_read else "#000000"
                decoration = "line-through" if is_read else "none"
                style = f"style='color:{color}; text-decoration:{decoration}; font-size:13px;'"
                
                r_cols[1].markdown(f"<p {style}>{u}</p>", unsafe_allow_html=True)
                r_cols[2].markdown(f"<p {style}>{row['原因']}</p>", unsafe_allow_html=True)
                r_cols[3].markdown(f"<p {style}>{row['个人实际销量']:.2f}</p>", unsafe_allow_html=True)
                r_cols[4].markdown(f"<p {style}>{int(row['投注单数'])}</p>", unsafe_allow_html=True)
                r_cols[5].markdown(f"<p {style}>{row['个人游戏盈亏']:.2f}</p>", unsafe_allow_html=True)
                r_cols[6].markdown(f"<p {style}>{row['RTP']:.4f}</p>", unsafe_allow_html=True)

        st.write("---")
        csv_data = res.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出分析结果", csv_data, "ghost_audit_v19.csv", "text/csv")
    elif res is not None:
        st.success("✅ 没有发现符合设定条件的用户。")
else:
    st.info("👋 请先在左侧设定规则并上传 Excel 文件。")
