"""
Quick script to analyze the timing data from terminal output.
"""

timing_data = [
    {"function": "assemble_page_templates_level1", "count": 1, "total_seconds": 3880.13, "avg_seconds": 3880.13, "max_seconds": 3880.13, "min_seconds": 3880.13},
    {"function": "add_records_for_page", "count": 90, "total_seconds": 3089.84, "avg_seconds": 34.33, "max_seconds": 123.42, "min_seconds": 0.11},
    {"function": "publishPage", "count": 26, "total_seconds": 280.96, "avg_seconds": 10.81, "max_seconds": 25.55, "min_seconds": 6.76},
    {"function": "psPublishApi", "count": 26, "total_seconds": 228.45, "avg_seconds": 8.79, "max_seconds": 23.53, "min_seconds": 4.74},
    {"function": "pre_download_all_components", "count": 1, "total_seconds": 116.05, "avg_seconds": 116.05, "max_seconds": 116.05, "min_seconds": 116.05},
    {"function": "updatePageMapping", "count": 26, "total_seconds": 71.75, "avg_seconds": 2.76, "max_seconds": 3.91, "min_seconds": 2.33},
    {"function": "CreatePage", "count": 26, "total_seconds": 45.38, "avg_seconds": 1.75, "max_seconds": 2.63, "min_seconds": 1.21},
    {"function": "psMappingApi", "count": 26, "total_seconds": 45.26, "avg_seconds": 1.74, "max_seconds": 2.90, "min_seconds": 1.32},
    {"function": "GetAllVComponents", "count": 1, "total_seconds": 7.63, "avg_seconds": 7.63, "max_seconds": 7.63, "min_seconds": 7.63},
]

print("\n" + "="*110)
print("TIMING ANALYSIS - Performance Metrics (Converted to Minutes)")
print("="*110)

print(f"\n{'Function':<40} {'Count':<8} {'Total (min)':<15} {'Avg (min)':<15} {'Max (min)':<15} {'Min (min)':<15} {'% of Total':<12}")
print("-"*110)

total_time = sum(item["total_seconds"] for item in timing_data)

for item in timing_data:
    total_min = item["total_seconds"] / 60.0
    avg_min = item["avg_seconds"] / 60.0
    max_min = item["max_seconds"] / 60.0
    min_min = item["min_seconds"] / 60.0
    percentage = (item["total_seconds"] / total_time) * 100
    
    print(f"{item['function']:<40} {item['count']:<8} {total_min:<15.2f} {avg_min:<15.2f} {max_min:<15.2f} {min_min:<15.2f} {percentage:<12.1f}%")

print("-"*110)
print(f"\n[TOTAL PROCESSING TIME] {total_time / 60:.2f} minutes ({total_time:.2f} seconds)")
print("="*110)

print("\n[TOP 5 SLOWEST FUNCTIONS BY TOTAL TIME]")
print("-"*110)
for i, item in enumerate(timing_data[:5], 1):
    total_min = item["total_seconds"] / 60.0
    avg_min = item["avg_seconds"] / 60.0
    max_min = item["max_seconds"] / 60.0
    min_min = item["min_seconds"] / 60.0
    percentage = (item["total_seconds"] / total_time) * 100
    
    print(f"\n{i}. {item['function']}")
    print(f"   Total: {total_min:.2f} min ({item['total_seconds']:.2f} sec) - {percentage:.1f}% of total time")
    print(f"   Average: {avg_min:.2f} min per call")
    print(f"   Called: {item['count']} times")
    print(f"   Max: {max_min:.2f} min, Min: {min_min:.2f} min")

print("\n" + "="*110)
print("\n[KEY INSIGHTS]")
print("-"*110)
print(f"1. assemble_page_templates_level1 takes {timing_data[0]['total_seconds']/60:.2f} min ({timing_data[0]['total_seconds']/total_time*100:.1f}%) - This is the main assembly function")
print(f"2. add_records_for_page takes {timing_data[1]['total_seconds']/60:.2f} min ({timing_data[1]['total_seconds']/total_time*100:.1f}%) - Called 90 times, avg {timing_data[1]['avg_seconds']:.2f}s per call")
print(f"3. Combined, these two functions account for {(timing_data[0]['total_seconds'] + timing_data[1]['total_seconds'])/total_time*100:.1f}% of total processing time")
print(f"4. Publishing operations (publishPage + psPublishApi) take {(timing_data[2]['total_seconds'] + timing_data[3]['total_seconds'])/60:.2f} min total")
print("="*110 + "\n")



