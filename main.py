from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import re
import random
from bs4 import BeautifulSoup
import html as html_lib
import yt_dlp
from user_agent import generate_user_agent
import os
import instaloader
from pinterest_downloader import Pinterest
from extra import extra_bp

app = Flask(__name__)

app.register_blueprint(extra_bp)
CORS(app)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

# ============================================================
# FACEBOOK
# ============================================================
def get_fb_video(url):
    headers = {
        'User-Agent': generate_user_agent(),
        'Origin': 'https://fbdown.blog',
        'Referer': 'https://fbdown.blog/',
    }
    try:
        r = requests.post('https://fbdown.blog/get.php', headers=headers, data={'url': url}, timeout=15)
        raw = r.text.replace('\\/', '/')
        data = r.json()['data']
        title = data.get("title", "Unknown Title")
        author = data.get("author", "Unknown Author")
        duration_sec = data.get("duration", 0)
        thumbnail = data.get("thumbnail", "")
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        duration_str = f"{mins:02d}:{secs:02d}"
        hd = sd = "Not available"
        for m in data.get("medias", []):
            if m.get("quality") == "HD":
                hd = m["url"]
            elif m.get("quality") == "SD" and sd == "Not available":
                sd = m["url"]
        return {
            "status": "success",
            "video": {
                "title": title,
                "author": author,
                "duration": duration_str,
                "thumbnail": thumbnail,
                "hd": hd,
                "sd": sd
            },
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }
    except:
        return {
            "status": "error",
            "message": "Facebook video not found",
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }

# ============================================================
# INSTAGRAM REELS
# ============================================================
def download_insta_reel(url):
    try:
        # URL থেকে shortcode বের করা (যেমন: reel/ABC123/ থেকে ABC123)
        match = re.search(r'instagram\.com/(?:p|reel|tv)/([^/?#]+)', url)
        if not match:
            return {
                "status": "error",
                "message": "Invalid Instagram URL. Please provide a post or reel link.",
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }
        
        shortcode = match.group(1)
        
        # Instaloader ইনিশিয়ালাইজ করা (লগইন ছাড়াই পাবলিক কন্টেন্টের জন্য)
        L = instaloader.Instaloader()
        
        # নির্দিষ্ট পোস্ট/রিল ফেচ করা
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # ডাউনলোডযোগ্য ভিডিও URL এবং অন্যান্য মেটাডেটা বের করা
        video_url = post.video_url
        caption = post.caption or "Instagram Media"
        owner = post.owner_username
        thumbnail = post.url  # এটি ইমেজের URL
        
        if not video_url:
            return {
                "status": "error",
                "message": "No video found in this post.",
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }
        
        return {
            "Developer": "M. Sarker",
            "Download Link": video_url,
            "Quality": "Original",
            "Title": caption,
            "Thumbnail": thumbnail,
            "Author": owner,
            "Owner": "SARKER"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Instagram request failed: {str(e)}",
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }

# ============================================================
# TIKTOK (No Watermark)
# ============================================================
def download_tiktok(url):
    try:
        if not url:
            return {"status": "error", "message": "TikTok URL is required", "Developer": "M. Sarker", "Owner": "SARKER"}
        
        # tikwm.com ফ্রি API ব্যবহার করে TikTok ডেটা ফেচ করা হচ্ছে
        api_url = "https://www.tikwm.com/api/"
        params = {"url": url, "hd": 1}
        
        response = requests.get(api_url, params=params, timeout=15)
        res_data = response.json()
        
        if res_data.get("code") != 0:
            return {"status": "error", "message": "Failed to fetch TikTok data. Invalid URL.", "Developer": "M. Sarker", "Owner": "SARKER"}
            
        data = res_data.get("data", {})
        
        # No Watermark ভিডিও লিংক (HD অথবা Normal)
        video_url = data.get("hdplay") or data.get("play") or data.get("wmplay")
        title = data.get("title", "TikTok Video")
        author = data.get("author", {}).get("unique_id", "Unknown")
        thumbnail = data.get("origin_cover") or data.get("cover")
        
        if not video_url:
                return {"status": "error", "message": "No video found in this TikTok post", "Developer": "M. Sarker", "Owner": "SARKER"}

        return {
            "status": "success",
            "title": title,
            "author": author,
            "thumbnail": thumbnail,
            "video": [{"quality": "HD (No Watermark)", "ext": "mp4", "url": video_url}],
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }
    except Exception as e:
        return {"status": "error", "message": f"TikTok request failed: {str(e)}", "Developer": "M. Sarker", "Owner": "SARKER"}

# ============================================================
# PINTEREST
# ============================================================
def get_pinterest_download_links(url):
    try:
        p = Pinterest()
        result = p.get_pin(url)
        
        if not result.get("ok"):
            return {
                "status": "error",
                "message": "Invalid Pinterest URL or no media found",
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }
        
        pin = result["pin"]
        media_type = pin.get("media_type")
        
        if media_type == "video":
            # ভিডিও ফরম্যাটগুলোর মধ্যে প্রথমটি নেওয়া হচ্ছে
            video_formats = pin.get("video", {}).get("formats", [])
            if not video_formats:
                return {
                    "status": "error",
                    "message": "No video formats found",
                    "Developer": "M. Sarker",
                    "Owner": "SARKER"
                }
            download_url = video_formats[0].get("url")
            return {
                "status": "success",
                "video": download_url,
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }
        elif media_type in ["image", "gif"]:
            # ইমেজের মূল URL নেওয়া হচ্ছে
            image_url = pin.get("images", {}).get("orig", {}).get("url")
            if not image_url:
                return {
                    "status": "error",
                    "message": "No image found",
                    "Developer": "M. Sarker",
                    "Owner": "SARKER"
                }
            return {
                "status": "success",
                "photo": image_url,
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }
        else:
            return {
                "status": "error",
                "message": "Unsupported media type",
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Pinterest request failed: {str(e)}",
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }

# ============================================================
# YOUTUBE
# ============================================================

def download_youtube(url):
    try:
        if not url:
            return {
                "status": "error",
                "message": "YouTube URL is required",
                "Developer": "M. Sarker",
                "Owner": "SARKER"
            }

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
            "format": "all"
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []
        seen_urls = set()

        for f in info.get("formats", []):
            direct_url = f.get("url")
            if not direct_url or direct_url in seen_urls:
                continue

            seen_urls.add(direct_url)
            
            # vcodec এবং acodec পাঠানো হচ্ছে যাতে ফ্রন্টএন্ডে অডিও/ভিডিও আলাদা করা যায়
            formats.append({
                "quality": f.get("format_note") or f.get("resolution") or f.get("format") or "Original",
                "ext": f.get("ext") or "mp4",
                "url": direct_url,
                "vcodec": f.get("vcodec", "none"),
                "acodec": f.get("acodec", "none")
            })

        return {
            "status": "success",
            "title": info.get("title", "Unknown Title"),
            "author": info.get("uploader", "Unknown"),
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "video": formats,
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"YouTube request failed: {str(e)}",
            "Developer": "M. Sarker",
            "Owner": "SARKER"
        }

# ============================================================
# ROUTES
# ============================================================

# @app.route('/', methods=['GET'])
# def index():
#     return jsonify({
#         "Developer": "M. Sarker",
#         "Endpoints": {
#             "Facebook": "/facebook?video=URL",
#             "Instagram": "/Instagram?video=URL",
#             "Pinterest": "/Pinterest?video=URL",
#             "TikTok": "/tiktok?video=URL",
#             "YouTube": "/youtube?video=URL"
#         },
#         "Owner": "SARKER"
#     })

# @app.route('/panel', methods=['GET'])
# def panel():
#     base = os.path.dirname(os.path.abspath(__file__))
#     with open(os.path.join(base, 'panel.html'), 'r', encoding='utf-8') as f:
#         return f.read()

@app.route('/', methods=['GET'])
def home():
    base = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(base, 'index.html'), 'r', encoding='utf-8') as f:
        return f.read()

# @app.route('/api', methods=['GET'])
# def api_info():
#     return jsonify({
#         "Developer": "M. Sarker",
#         "Endpoints": {
#             "Facebook": "/facebook?video=URL",
#             "Instagram": "/Instagram?video=URL",
#             "Pinterest": "/Pinterest?video=URL",
#             "TikTok": "/tiktok?video=URL",
#             "YouTube": "/youtube?video=URL"
#         },
#         "Owner": "SARKER"
#     })

@app.route('/facebook', methods=['GET', 'POST'])
def fb(): return jsonify(get_fb_video(request.values.get("video", "").strip()))

@app.route('/Instagram', methods=['GET', 'POST'])
def insta(): return jsonify(download_insta_reel(request.values.get("video", "").strip()))

@app.route('/tiktok', methods=['GET', 'POST'])
def tiktok():
    return jsonify(download_tiktok(request.values.get("video", "").strip()))

@app.route('/Pinterest', methods=['GET', 'POST'])
def pin(): return jsonify(get_pinterest_download_links(request.values.get("video", "").strip()))


@app.route('/youtube', methods=['GET', 'POST'])
def youtube():
    return jsonify(download_youtube(request.values.get("video", "").strip()))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)