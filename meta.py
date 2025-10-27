import requests

url = "https://www.metacareers.com/graphql"

payload = 'av=0&__user=0&__a=1&__req=3&__hs=20359.BP%3ADEFAULT.2.0...0&dpr=2&__ccg=EXCELLENT&__rev=1027711479&__s=2tw6ye%3Aj1nybu%3Ax9zv2z&__hsi=7555259671671314312&__dyn=7xeUmwkHg7ebwKBAg5S1Dxu13wqovzEdEc8uxa1twKzobo1nEhw2nVE4W0qa0FE662y0um4o5-0ha2l0Fw78waO0IopyE3bwkE5G0zE5W0HU1IEGdxa0YU2ZwrU6C0P82Sw8i19w4kwtU5K6o7m1iw2ho&__hsdp=8dEcgAgTBgaNieOLwzgkJJ286u2St2WG2218xq78aA0k90ko7K0rq2K0kF261qw4GghxK1Bwi42q1Bway1Da2gg3e07Z8&__hblp=0UwaK1TwTw6ew7_wfS2i0km09kw4KwAwaK0csw2o87F00h1U0hww8i1Hw3FEGAro621kCDyVE980qnw4Zw2t8&lsd=AdEh6vHilLo&jazoest=2982&__spin_r=1027711479&__spin_b=trunk&__spin_t=1759095972&__jssesw=1&fb_api_caller_class=RelayModern&fb_api_req_friendly_name=CareersJobSearchResultsDataQuery&variables=%7B%22search_input%22%3A%7B%22q%22%3Anull%2C%22divisions%22%3A%5B%5D%2C%22offices%22%3A%5B%22Seattle%2C%20WA%22%2C%22Menlo%20Park%2C%20CA%22%2C%22New%20York%2C%20NY%22%5D%2C%22roles%22%3A%5B%22Full%20time%20employment%22%5D%2C%22leadership_levels%22%3A%5B%5D%2C%22saved_jobs%22%3A%5B%5D%2C%22saved_searches%22%3A%5B%5D%2C%22sub_teams%22%3A%5B%5D%2C%22teams%22%3A%5B%22Artificial%20Intelligence%22%2C%22Product%20Management%22%5D%2C%22is_leadership%22%3Afalse%2C%22is_remote_only%22%3Afalse%2C%22sort_by_new%22%3Atrue%2C%22results_per_page%22%3Anull%7D%7D&server_timestamps=true&doc_id=29615178951461218'
headers = {
  'accept': '*/*',
  'accept-language': 'en-US,en;q=0.9',
  'cache-control': 'no-cache',
  'content-type': 'application/x-www-form-urlencoded',
  'origin': 'https://www.metacareers.com',
  'pragma': 'no-cache',
  'priority': 'u=1, i',
  'referer': 'https://www.metacareers.com/jobs?sort_by_new=true&teams[0]=Artificial%20Intelligence&teams[1]=Product%20Management&roles[0]=Full%20time%20employment&offices[0]=Seattle%2C%20WA&offices[1]=Menlo%20Park%2C%20CA&offices[2]=New%20York%2C%20NY',
  'sec-ch-ua': '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"macOS"',
  'sec-fetch-dest': 'empty',
  'sec-fetch-mode': 'cors',
  'sec-fetch-site': 'same-origin',
  'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
  'x-asbd-id': '359341',
  'x-fb-friendly-name': 'CareersJobSearchResultsDataQuery',
  'x-fb-lsd': 'AdEh6vHilLo',
  'Cookie': 'datr=EqzZaNZqt0cNnVDZ0jYVZwmO; wd=1800x527'
}

response = requests.request("POST", url, headers=headers, data=payload)

print(response.json())
