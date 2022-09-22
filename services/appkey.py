import hashlib
import urllib.parse


def appsign(params):
    '为请求参数进行 api 签名'
    params.update({'appkey': appkey})
    params = dict(sorted(params.items())) # 重排序参数 key
    query = urllib.parse.urlencode(params) # 序列化参数
    sign = hashlib.md5((query+appsec).encode()).hexdigest() # 计算 api 签名
    params.update({'sign':sign})
    return params


appkey = '1d8b6e7d45233436'
appsec = '560c52ccd288fed045859ed18bffd973'
params = {
    'id':114514,
    'str':'1919810',
    'test':'いいよ，こいよ',
}


# signed_params = appsign(params, appkey, appsec)
# query = urllib.parse.urlencode(signed_params)
# print(signed_params)
# print(query)