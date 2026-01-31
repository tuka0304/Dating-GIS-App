from geopy.distance import geodesic
import requests

class DatingGISTool:
    """
    Bộ công cụ xử lý GIS chuyên biệt cho ứng dụng hẹn hò.
    Chức năng: 
    1. Tính khoảng cách Geodesic (chính xác hơn Haversine).
    2. Lọc không gian (Spatial Filter) theo bán kính.
    3. Tìm đường đi ngắn nhất (Routing) qua API OSRM.
    """
    
    @staticmethod
    def calculate_distance(point_a, point_b):
        """
        Hàm tính khoảng cách giữa 2 điểm tọa độ (lat, lon).
        Input: point_a=(lat1, lon1), point_b=(lat2, lon2)
        Output: Khoảng cách (km) làm tròn 2 chữ số thập phân.
        """
        # Sử dụng thư viện geopy để tính khoảng cách đường cong trái đất
        return round(geodesic(point_a, point_b).km, 2)

    @staticmethod
    def find_users_in_radius(center_point, user_list, radius_km):
        """
        Hàm lọc không gian: Tìm các user nằm trong bán kính cho trước.
        Input: 
            - center_point: Tọa độ tâm (Người dùng hiện tại)
            - user_list: Danh sách tất cả user trong DB
            - radius_km: Bán kính tìm kiếm (km)
        Output: List các user thỏa mãn điều kiện (đã được gán thêm thuộc tính distance)
        """
        valid_users = []
        
        for profile in user_list:
            # Lấy tọa độ của người cần kiểm tra
            target_point = (profile.latitude, profile.longitude)
            
            # Gọi hàm tính khoảng cách ở trên (Tái sử dụng code)
            dist = DatingGISTool.calculate_distance(center_point, target_point)
            
            # Kiểm tra điều kiện bán kính
            if dist <= radius_km:
                # Gán thêm thuộc tính 'distance_km' vào object để hiển thị ra giao diện sau này
                profile.distance_km = dist 
                valid_users.append(profile)
        
        # Sắp xếp danh sách: Người gần nhất lên đầu (Sort by distance)
        valid_users.sort(key=lambda x: x.distance_km)
        
        return valid_users

    @staticmethod
    def get_routing_geometry(start_point, end_point):
        """
        Hàm tìm đường: Gọi API OSRM để lấy dữ liệu vẽ đường đi ngắn nhất.
        Input: start_point (lat, lon), end_point (lat, lon)
        Output: GeoJSON geometry (để Leaflet vẽ lên bản đồ) hoặc None nếu lỗi.
        """
        # Lưu ý: OSRM yêu cầu format tọa độ là: longitude,latitude (Ngược với Google Maps)
        str_start = f"{start_point[1]},{start_point[0]}"
        str_end = f"{end_point[1]},{end_point[0]}"
        
        # URL gọi API (OSRM Demo Server - Miễn phí, không cần Key)
        url = f"http://router.project-osrm.org/route/v1/driving/{str_start};{str_end}?overview=full&geometries=geojson"
        
        try:
            # Gửi yêu cầu HTTP GET lên server
            resp = requests.get(url, timeout=5)
            data = resp.json()
            
            # Kiểm tra kết quả trả về
            if data.get('code') == 'Ok':
                return data['routes'][0]['geometry'] # Trả về dữ liệu hình học để vẽ
        except Exception as e:
            print(f"Lỗi API GIS: {e}")
        
        return None