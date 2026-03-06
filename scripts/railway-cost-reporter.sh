#!/bin/bash

# Railway 料金レポーター
# 毎朝 10:00 UTC に実行して Railway の使用量と予測料金を C0AHUGG1C82 に送信

set -euo pipefail

RAILWAY_TOKEN=$(op read "op://banana/railway/password")
WORKSPACE_ID="d327b30e-dbc7-489d-a9be-9b0291afedb8"
SLACK_CHANNEL="C0AHUGG1C82"

# 日付計算
START_DATE=$(date -u -d "$(date -u +%Y-%m-01)" +%Y-%m-%dT00:00:00Z)
END_DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)

echo "Rail way 料金レポートを取得中..." >&2

# API レスポンスを一度ファイルに保存
TMPFILE=$(mktemp)
trap "rm -f $TMPFILE" EXIT

curl -s -X POST "https://backboard.railway.com/graphql/internal?q=allProjectCurrentUsage" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -d @- > "$TMPFILE" << EOF
{
  "query": "query allProjectCurrentUsage(\$workspaceId: String, \$usageMeasurements: [MetricMeasurement!]!, \$startDate: DateTime!, \$endDate: DateTime!, \$includeDeleted: Boolean, \$useSmallDateChunks: Boolean) { usage(workspaceId: \$workspaceId, measurements: \$usageMeasurements, groupBy: [PROJECT_ID], startDate: \$startDate, endDate: \$endDate, includeDeleted: \$includeDeleted, useSmallDateChunks: \$useSmallDateChunks) { measurement value tags { projectId } } projects(first: 5000, includeDeleted: true, workspaceId: \$workspaceId) { edges { node { id name } } } }",
  "variables": {
    "workspaceId": "$WORKSPACE_ID",
    "usageMeasurements": ["MEMORY_USAGE_GB", "CPU_USAGE", "NETWORK_TX_GB", "DISK_USAGE_GB", "BACKUP_USAGE_GB"],
    "startDate": "$START_DATE",
    "endDate": "$END_DATE",
    "includeDeleted": true,
    "useSmallDateChunks": true
  }
}
EOF

# Python で集計と料金計算
python3 << 'PYTHON_EOF'
import json
import sys
from collections import defaultdict
from datetime import datetime

try:
    with open(sys.argv[1], 'r') as f:
        data = json.load(f)
    
    if 'errors' in data or 'error' in data:
        print("❌ エラー: API から料金データを取得できませんでした")
        sys.exit(1)
    
    # プロジェクト名マップ
    project_map = {}
    for edge in data.get('data', {}).get('projects', {}).get('edges', []):
        node = edge.get('node', {})
        project_map[node.get('id')] = node.get('name', 'Unknown')
    
    # プロジェクト別に集計
    project_usage = defaultdict(lambda: {
        'CPU_USAGE': 0,
        'MEMORY_USAGE_GB': 0,
        'NETWORK_TX_GB': 0,
        'DISK_USAGE_GB': 0,
        'BACKUP_USAGE_GB': 0,
    })
    
    for item in data.get('data', {}).get('usage', []):
        project_id = item.get('tags', {}).get('projectId')
        measurement = item.get('measurement')
        value = item.get('value', 0)
        
        if project_id and measurement in project_usage[project_id]:
            project_usage[project_id][measurement] += value
    
    # 料金計算
    results = {}
    total_usd = 0
    
    for project_id, usage in project_usage.items():
        project_name = project_map.get(project_id, project_id[:8])
        
        cpu_cost = usage['CPU_USAGE'] * 0.000278
        memory_cost = usage['MEMORY_USAGE_GB'] * 0.000086
        network_cost = usage['NETWORK_TX_GB'] * 0.02
        disk_cost = usage['DISK_USAGE_GB'] * 0.125 / 30
        backup_cost = usage['BACKUP_USAGE_GB'] * 0.05 / 30
        
        project_total = cpu_cost + memory_cost + network_cost + disk_cost + backup_cost
        
        results[project_name] = {
            'cpu': cpu_cost,
            'memory': memory_cost,
            'network': network_cost,
            'disk': disk_cost,
            'backup': backup_cost,
            'total': project_total,
        }
        
        total_usd += project_total
    
    # メッセージ出力
    total_jpy = total_usd * 130
    today = datetime.utcnow().strftime("%Y年%m月%d日")
    
    message = f"💰 Railway 料金レポート - {today}\n\n"
    message += f"📊 予測月額合計: ¥{total_jpy:,.0f} (${total_usd:.2f})\n\n"
    message += "プロジェクト別内訳：\n\n"
    
    for project_name in sorted(results.keys()):
        cost = results[project_name]
        project_jpy = cost['total'] * 130
        
        message += f"🔹 {project_name}\n"
        message += f"  CPU: ${cost['cpu']:.4f}\n"
        message += f"  Memory: ${cost['memory']:.4f}\n"
        message += f"  Network: ${cost['network']:.4f}\n"
        message += f"  Disk: ${cost['disk']:.4f}\n"
        message += f"  Backup: ${cost['backup']:.4f}\n"
        message += f"  **小計**: ${cost['total']:.4f} (≈ ¥{project_jpy:,.0f})\n\n"
    
    print(message)
    
except Exception as e:
    print(f"❌ エラー: {str(e)}")
    sys.exit(1)

PYTHON_EOF "$TMPFILE"
