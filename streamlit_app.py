import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import numpy as np
from haversine import haversine, Unit
import requests

st.title("🏨 서울 호텔 + 주변 관광지 시각화")

# 🔑 API Key
api_key = "f0e46463ccf90abd0defd9c79c8568e922e07a835961b1676cdb2065ecc23494"

# -------------------
# 1) 호텔 정보 가져오기
# -------------------
@st.cache_data(ttl=3600)
def get_hotels(api_key):
    url = "http://apis.data.go.kr/B551011/KorService2/searchStay2"
    params = {
        "ServiceKey": api_key,
        "numOfRows": 50,
        "pageNo": 1,
        "MobileOS": "ETC",
        "MobileApp": "hotel_analysis",
        "arrange": "A",
        "_type": "json",
        "areaCode": 1  # 서울
    }
    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        items = data['response']['body']['items']['item']
        df = pd.DataFrame(items)
    except Exception as e:
        st.error(f"호텔 API 호출 실패: {e}")
        return pd.DataFrame(columns=['name','lat','lng','price','rating'])

    for col in ['title','mapx','mapy']:
        if col not in df.columns:
            df[col] = None
    df = df[['title','mapx','mapy']].rename(columns={'title':'name','mapx':'lng','mapy':'lat'})
    df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
    df['lng'] = pd.to_numeric(df['lng'], errors='coerce')
    df = df.dropna(subset=['lat','lng'])
    df['price'] = np.random.randint(150000, 300000, size=len(df))
    df['rating'] = np.random.uniform(3.0,5.0, size=len(df)).round(1)
    return df

hotels_df = get_hotels(api_key)
if hotels_df.empty:
    st.warning("호텔 정보를 불러오지 못했습니다. API Key와 네트워크를 확인하세요.")
    st.stop()

# -------------------
# 2) 호텔 선택
# -------------------
hotel_names = hotels_df['name'].tolist()
selected_hotel = st.selectbox("호텔 선택", hotel_names)
hotel_info = hotels_df[hotels_df['name']==selected_hotel].iloc[0]

# -------------------
# 3) 두 CSV 파일 통합
# -------------------
@st.cache_data(ttl=3600)
def load_and_merge_tourist(csv_file1, csv_file2):
    dfs = []
    for csv_file, mapping in zip(
        [csv_file1, csv_file2],
        [
            {'lng':'중심 좌표 X','lat':'중심 좌표 Y','name':'최종 표기명'},
            {'lng':'X 좌표','lat':'Y 좌표','name':'명칭'}
        ]
    ):
        try:
            df = pd.read_csv(csv_file, encoding='cp949')  # <- 여기만 수정
            for new_col, old_col in mapping.items():
                if old_col in df.columns:
                    df[new_col] = pd.to_numeric(df[old_col], errors='coerce') if new_col in ['lat','lng'] else df[old_col]
                else:
                    df[new_col] = np.nan
            df = df.dropna(subset=['lat','lng'])
            df = df[['name','lat','lng']]
            dfs.append(df)
        except Exception as e:
            st.warning(f"{csv_file} 처리 중 오류: {e}")
            dfs.append(pd.DataFrame(columns=['name','lat','lng']))
    merged_df = pd.concat(dfs, ignore_index=True)
    return merged_df


tourist_df = load_and_merge_tourist(
    "서울시 관광거리 정보 (한국어)(2015년).csv",
    "서울시 종로구 관광데이터 정보 (한국어).csv"
)

if tourist_df.empty:
    st.warning("관광지 데이터를 불러오지 못했습니다.")
    st.stop()

# -------------------
# 4) 호텔 반경 내 관광지 필터링
# -------------------
radius_m = st.slider("관광지 반경 (m)", 500, 2000, 1000, step=100)

def get_nearby_tourist(hotel_lat, hotel_lng, tourist_df, radius_m):
    nearby = []
    for idx, row in tourist_df.iterrows():
        distance = haversine((hotel_lat, hotel_lng), (row['lat'], row['lng']), unit=Unit.METERS)
        if distance <= radius_m:
            nearby.append(row)
    return pd.DataFrame(nearby)

nearby_tourist_df = get_nearby_tourist(hotel_info['lat'], hotel_info['lng'], tourist_df, radius_m)

# -------------------
# 5) 지도 시각화
# -------------------
m = folium.Map(location=[hotel_info['lat'], hotel_info['lng']], zoom_start=15)

# 호텔 마커
folium.Marker(
    location=[hotel_info['lat'], hotel_info['lng']],
    popup=f"{hotel_info['name']} | 가격: {hotel_info['price']} | 별점: {hotel_info['rating']}",
    icon=folium.Icon(color='red', icon='hotel', prefix='fa')
).add_to(m)

# 관광지 마커
for idx, row in nearby_tourist_df.iterrows():
    folium.CircleMarker(
        location=[row['lat'], row['lng']],
        radius=4,
        color='blue',
        fill=True,
        fill_opacity=0.7,
        popup=row['name']
    ).add_to(m)

st.subheader(f"{selected_hotel} 주변 관광지 지도")
st_folium(m, width=700, height=500, returned_objects=[])

# -------------------
# 6) 호텔 정보 + 관광지 목록
# -------------------
st.subheader("호텔 정보 및 주변 관광지")
st.write(f"**호텔명:** {hotel_info['name']}")
st.write(f"**가격:** {hotel_info['price']}원")
st.write(f"**별점:** {hotel_info['rating']}")
st.write(f"**주변 관광지 수:** {len(nearby_tourist_df)}")
st.dataframe(nearby_tourist_df[['name']])
