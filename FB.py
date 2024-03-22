import requests
import json
import smtplib

# 異常通知者
admin_addr = ['']
# 預設為空
access_token = ''

class Post:
    def __init__(self, data) -> None:
        self.post_id = data.get('id', None)
        self.views = data.get('views', 0)
        self.description = data.get('description', '')
        self.created_time = data.get('created_time', '')
        comments = data.get('comments', [])

        self.comments_count = 0
        if comments:
            self.comments_count = comments['summary']['total_count']

        likes = data.get('likes', [])
        if likes:
            self.likes_count = likes['summary']['total_count']

        video_insights = data.get('video_insights', '')

        self.shares = 0
        if video_insights:
            vi_datas = video_insights['data']
            for vi_data in vi_datas:
                if vi_data['name'] == 'post_video_social_actions':
                    values = vi_data.get('values', [])
                    if values:
                        self.shares = values[0]['value'].get('SHARE', 0)
                    break

    def __repr__(self) -> str:
        return f'created time: {self.created_time}, description : {self.description[:10]} ..., views : {self.views}, comments count : {self.comments_count}, shares : {self.shares}'


class IGPost:
    def __init__(self, data) -> None:
        self.id = data.get('id', None)
        self.media_type = data.get('media_type', None)
        self.created_time = data.get('timestamp', None)
        self.title = data.get('caption', None)
        self.saved = 0
        self.shares = 0
        self.plays = 0
        self.likes = 0
        self.comments_count = 0
        for insight_data in data['insights']['data']:
            if insight_data['name'] == 'saved':
                if insight_data.get('values', None):
                    self.saved = insight_data['values'][0].get('value', 0)
            if insight_data['name'] == 'plays':
                if insight_data.get('values', None):
                    self.plays = insight_data['values'][0].get('value', 0)
            if insight_data['name'] == 'impressions':
                if insight_data.get('values', None):
                    self.plays = insight_data['values'][0].get('value', 0)
            if insight_data['name'] == 'shares':
                if insight_data.get('values', None):
                    self.shares = insight_data['values'][0].get('value', 0)
            if insight_data['name'] == 'likes':
                if insight_data.get('values', None):
                    self.likes = insight_data['values'][0].get('value', 0)
            if insight_data['name'] == 'comments':
                if insight_data.get('values', None):
                    self.comments_count = insight_data['values'][0].get('value', 0)
    
    def __repr__(self) -> str:
        return f'created time : {self.created_time}, title : {self.title[:10]} ..., plays : {self.plays}, comments count : {self.comments_count}, likes : {self.likes}, shares : {self.shares}'


class Account:
    '''
        trans json to id, access_token, name
    '''
    def __init__(self, data) -> None:
        self.id = data.get('id', None)
        self.access_token = data.get('access_token', None)
        self.name = data.get('name', None)
        self.posts = []
        self.ig_posts = []
        instagram_business_account = data.get('instagram_business_account', None)
        if instagram_business_account:
            self.ig_id = instagram_business_account.get('id', None)
        else:
            self.ig_id = None

    def __repr__(self) -> str:
        return f'account id : {self.id}, name : {self.name}, ig id : {self.ig_id}'


class FB:
    '''
        facebook graphQL api object
        you need to input access token when FB class init
    '''

    base_url = 'https://graph.facebook.com'

    def __init__(self, access_token: str=access_token, version: str='v19.0') -> None:
        self.access_token = access_token
        self.access_token_url = '?access_token='
        self.version = version
        self.url = self.base_url + '/' + self.version + '/'
        self.accounts: list[Account] = []

    def get_me_accounts(self) -> list[Account]:
        get_me_accounts_url = 'me/accounts'
        fields_url = '&fields=access_token,name,id,instagram_business_account'
        all_url = self.url + get_me_accounts_url + self.access_token_url + self.access_token + fields_url
        response = self._get_data_from_url(all_url)
        self._tran_accounts_data_json_to_Account(response['data'])
        return self.accounts

    def _tran_accounts_data_json_to_Account(self, datas: dict) -> list[Account]:
        for data in datas:
            self.accounts.append(Account(data))
        return self.accounts

    def get_videos_datas(self, max_page: int=5) -> list[Account]:
        videos_datas_url = '&fields=videos{id,created_time,description,views,comments.summary(1),likes.summary(1),video_insights}'
        for account in self.accounts:
            all_url = self.url + account.id + self.access_token_url + self.access_token + videos_datas_url
            response = self._get_data_from_url(all_url)
            self._tran_video_data_json_to_Post(account, response['videos']['data'])
            has_next, next_link = self.check_datas_have_next(response['videos'])
            self._get_next_paging_until_no_next(account, has_next, next_link, self._tran_video_data_json_to_Post, max_page)
        return self.accounts

    def _get_next_paging_until_no_next(self, account: Account, has_next: bool, next_link: str, deal_with_datas: callable, max_page: int=5) -> None:
        '''
            if has_next is True 抓取 next_link 的datas處理完後, 再重跑一次
            deal_with_datas: 會一個callable object 去處理所抓取的datas
            account: 為Account物件所有相關datas都應跟隨著Account
            max_page: 為next最大次數 預設為 5
        '''
        if max_page == 0:
            return
        if has_next:
            response = self._get_data_from_url(next_link)
            deal_with_datas(account, response['data'])
            has_next, next_link = self.check_datas_have_next(response)
            max_page -= 1
            self._get_next_paging_until_no_next(account, has_next, next_link, deal_with_datas, max_page)

    def _tran_video_data_json_to_Post(self, account: Account, datas: dict) -> None:
        for data in datas:
            account.posts.append(Post(data))

    def get_ig_posts_datas(self, max_page: int=5) -> list[Account]:
        ig_posts_url = '&fields=media{insights.metric(impressions,reach,engagement,saved,video_views,likes,comments,shares,plays,total_interactions),media_type,timestamp,caption}'
        for account in self.accounts:
            all_url = self.url + account.ig_id + self.access_token_url + self.access_token + ig_posts_url
            response = self._get_data_from_url(all_url)
            self._tran_ig_post_data_json_to_IGPost(account, response['media']['data'])
            has_next, next_link = self.check_datas_have_next(response['media'])
            self._get_next_paging_until_no_next(account, has_next, next_link, self._tran_ig_post_data_json_to_IGPost, max_page)
        return self.accounts
    
    def _tran_ig_post_data_json_to_IGPost(self, account: Account, datas: dict) -> None:
        for data in datas:
            account.ig_posts.append(IGPost(data))

    def check_datas_have_next(self, datas: dict) -> list[bool, str]:
        paging = datas.get('paging', '')
        next_link = paging.get('next', '')
        if next_link:
            has_next = True
        else:
            has_next = False
        return [has_next, next_link]

    def _get_data_from_url(self, url: str) -> dict | None:
        response = requests.get(url).text
        result = self._trans_response_to_json(response)
        error = result.get('error', '')
        if error:
            # smtp to admin
            send_email(result, admin_addr)
            raise Exception(result)
        else:
            return result

    def _trans_response_to_json(self, response: str) -> dict:
        return json.loads(response)



def send_email(message, to_addr):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.utils import formataddr
    
    with smtplib.SMTP('smtp.gmail.com', 587) as smtp:
        msg = MIMEMultipart()
        msg['From'] = formataddr(['FB api 異常通知',''])
        msg['Subject'] = "FB api 異常通知"
        msg.attach(MIMEText(str(message), "plain", "utf-8"))
        
        smtp.ehlo()
        smtp.starttls()
        smtp.login('','')
        
        from_addr = ''
        smtp.sendmail(from_addr, to_addr, msg.as_string())
