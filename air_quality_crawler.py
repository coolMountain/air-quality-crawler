#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
空气知音网站(air-level.com)爬虫程序
爬取全国城市空气质量数据和各监测站点详情

程序分为两个阶段：
阶段一：爬取所有城市名称和对应的二级链接首页
阶段二：进入二级链接获取该城市各监测站的空气质量数据
"""

import requests
from bs4 import BeautifulSoup
import time
import re
import random
from urllib.parse import urljoin

class AirQualityCrawler:
    def __init__(self, class_name="鸿班2201", name="崔翔", student_id="2206040013"):
        """初始化爬虫类
        
        Args:
            class_name: 班级名
            name: 姓名
            student_id: 学号
        """
        self.class_name = class_name
        self.name = name
        self.student_id = student_id
        self.base_url = "https://www.air-level.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }
        # 重试次数
        self.max_retries = 3
        
    def get_html(self, url, retries=0):
        """获取网页HTML内容，支持重试
        
        Args:
            url: 目标URL
            retries: 当前重试次数
            
        Returns:
            str: HTML内容，失败则返回None
        """
        try:
            # 随机延迟0.5-1.5秒，避免请求过快被封IP
            time.sleep(random.uniform(0.5, 1.5))
            
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = "utf-8"
            if response.status_code == 200:
                return response.text
            else:
                print(f"请求失败，状态码: {response.status_code}，URL: {url}")
                
                # 如果请求失败且未超过最大重试次数，则重试
                if retries < self.max_retries:
                    print(f"正在进行第 {retries + 1} 次重试...")
                    time.sleep(2 ** retries)  # 指数退避策略
                    return self.get_html(url, retries + 1)
                return None
        except requests.exceptions.RequestException as e:
            print(f"请求异常: {e}，URL: {url}")
            
            # 如果请求异常且未超过最大重试次数，则重试
            if retries < self.max_retries:
                print(f"正在进行第 {retries + 1} 次重试...")
                time.sleep(2 ** retries)  # 指数退避策略
                return self.get_html(url, retries + 1)
            return None
    
    def parse_cities(self, html):
        """解析首页获取所有城市及其链接
        
        Args:
            html: 首页HTML内容
            
        Returns:
            list: 城市信息列表，每个元素为(城市名, 链接)元组
        """
        if not html:
            print("HTML内容为空，无法解析城市列表")
            return []
            
        cities = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 查找所有以字母开头的段落，这些段落后面跟着城市列表
            letter_paragraphs = soup.find_all("p", string=lambda text: text and re.match(r"^[A-Z]\.", text.strip()))
            
            for p in letter_paragraphs:
                # 查找字母分类区域，它通常是一个div，包含字母标题和城市列表
                city_section = p.parent
                if city_section:
                    # 获取该区域内的所有链接，这些链接是城市链接
                    city_links = city_section.find_all("a")
                    for link in city_links:
                        city_name = link.text.strip()
                        city_url = link["href"]
                        cities.append((city_name, city_url))
            
            # 检查主要城市区域
            key_cities_section = soup.find(string=lambda text: text and "重点城市" in text)
            if key_cities_section:
                key_cities_parent = key_cities_section.parent
                if key_cities_parent:
                    # 获取重点城市区域的所有链接
                    for a in key_cities_parent.find_next_siblings():
                        links = a.find_all("a")
                        for link in links:
                            city_name = link.text.strip()
                            city_url = link["href"]
                            # 检查是否已经添加过该城市
                            if not any(name == city_name for name, _ in cities):
                                cities.append((city_name, city_url))
            
            # 从排行榜表格中获取城市链接
            ranking_tables = soup.find_all("table")
            for table in ranking_tables:
                rows = table.find_all("tr")[1:]  # 跳过表头
                for row in rows:
                    city_link = row.find("a")
                    if city_link:
                        city_name = city_link.text.strip()
                        city_url = city_link["href"]
                        # 检查是否已经添加过该城市
                        if not any(name == city_name for name, _ in cities):
                            cities.append((city_name, city_url))
            
            # 确保所有URL都是相对路径，以便后续拼接
            cities = [(name, url if url.startswith("/") else f"/{url}") for name, url in cities]
            
            return cities
        except Exception as e:
            print(f"解析城市列表时发生异常: {e}")
            return []
    
    def parse_stations(self, html, city_name):
        """解析城市页面获取所有监测站的空气质量数据
        
        Args:
            html: 城市页面HTML内容
            city_name: 城市名称，用于日志输出
            
        Returns:
            list: 监测站空气质量数据列表
        """
        if not html:
            print(f"HTML内容为空，无法解析城市 {city_name} 的监测站数据")
            return []
            
        stations = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            
            # 查找监测站表格
            tables = soup.find_all("table")
            if not tables:
                print(f"在城市 {city_name} 页面中未找到表格")
                return stations
                
            # 在城市页面中，通常第一个表格是监测站数据
            # 表格结构通常是：监测站|AQI|空气质量等级|PM2.5|PM10|首要污染物
            table = tables[0]
            rows = table.find_all("tr")
            
            if len(rows) <= 1:
                print(f"城市 {city_name} 的监测站表格内容不足")
                return stations
            
            # 提取表头，确认列的含义
            headers = [th.text.strip() for th in rows[0].find_all(["th", "td"])]
            
            # 跳过表头
            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) >= 3:  # 确保有足够的列
                    station_data = {}
                    
                    # 根据表头提取数据
                    for i, col in enumerate(cols):
                        if i < len(headers):  # 防止索引越界
                            header = headers[i]
                            value = col.text.strip()
                            station_data[header] = value
                    
                    # 如果没有按表头提取到，则使用默认列名
                    if not station_data:
                        station_name = cols[0].text.strip()
                        aqi = cols[1].text.strip()
                        air_quality = cols[2].text.strip()
                        
                        # 提取更多数据，如果有的话
                        pm25 = cols[3].text.strip() if len(cols) > 3 else "N/A"
                        pm10 = cols[4].text.strip() if len(cols) > 4 else "N/A"
                        main_pollutant = cols[5].text.strip() if len(cols) > 5 else "N/A"
                        
                        station_data = {
                            "监测站": station_name,
                            "AQI": aqi,
                            "空气质量等级": air_quality,
                            "PM2.5": pm25,
                            "PM10": pm10,
                            "首要污染物": main_pollutant
                        }
                    
                    stations.append(station_data)
                    
            return stations
        except Exception as e:
            print(f"解析城市 {city_name} 的监测站数据时发生异常: {e}")
            return []
    
    def crawl_phase1(self):
        """阶段一：爬取所有城市名称和对应城市的二级链接首页"""
        print(f"阶段一：{self.class_name}+{self.name}+{self.student_id}")
        print("爬取结果：")
        
        # 获取首页HTML
        html = self.get_html(self.base_url)
        if not html:
            print("获取首页失败")
            return None
        
        # 解析城市列表
        cities = self.parse_cities(html)
        
        if not cities:
            print("未能爬取到城市数据")
            return None
        
        # 显示爬取结果
        print(f"共爬取到 {len(cities)} 个城市:")
        for i, (city_name, city_url) in enumerate(cities, 1):
            full_url = urljoin(self.base_url, city_url)
            print(f"{i}. {city_name}: {full_url}")
            
        return cities
    
    def crawl_phase2(self, cities):
        """阶段二：进入二级链接获取该城市各监测站的空气质量数据
        
        Args:
            cities: 阶段一爬取的城市列表
        """
        print(f"\n阶段二：{self.class_name}+{self.name}+{self.student_id}")
        print("爬取结果：")
        
        if not cities:
            print("没有城市数据可爬取")
            return
        
        all_stations = {}
        
        # 爬取所有城市的监测站数据
        print(f"将爬取所有 {len(cities)} 个城市的监测站数据")
        
        for i, (city_name, city_url) in enumerate(cities, 1):
            # 构建完整URL
            full_url = urljoin(self.base_url, city_url)
            print(f"[{i}/{len(cities)}] 正在爬取城市: {city_name} ({full_url})")
            
            # 获取城市页面HTML
            html = self.get_html(full_url)
            if not html:
                print(f"获取城市 {city_name} 页面失败，跳过该城市")
                continue
            
            # 解析监测站数据
            stations = self.parse_stations(html, city_name)
            
            if not stations:
                print(f"未能解析到城市 {city_name} 的监测站数据")
                continue
                
            all_stations[city_name] = stations
            
            # 打印该城市的监测站数据
            print(f"城市 {city_name} 共有 {len(stations)} 个监测站:")
            for j, station in enumerate(stations, 1):
                # 构建站点信息字符串，处理可能缺失的字段
                station_info = f"  {j}. 站点: {station.get('监测站', 'N/A')}"
                
                for key in ['AQI', '空气质量等级', 'PM2.5', 'PM10', '首要污染物']:
                    if key in station:
                        station_info += f", {key}: {station[key]}"
                
                print(station_info)
            
        return all_stations

def main():
    """主函数"""
    try:
        # 创建爬虫实例
        crawler = AirQualityCrawler()
        
        # 执行阶段一爬取
        print("开始执行阶段一爬取...")
        cities = crawler.crawl_phase1()
        
        # 执行阶段二爬取
        if cities:
            print("\n开始执行阶段二爬取...")
            crawler.crawl_phase2(cities)  # 直接爬取所有城市，不需要用户交互
        
        print("\n爬取完成！")
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序执行过程中发生异常: {e}")

if __name__ == "__main__":
    main()