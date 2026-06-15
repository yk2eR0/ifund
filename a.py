import akshare as ak
code = '110022'  # 示例基金代码
frame = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势')
print(frame.head())
print(frame.columns)