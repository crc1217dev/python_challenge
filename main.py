from flask import Flask, render_template, request

from scrapper import search_jobs


app = Flask("JobScrapper")


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/search")
def search():
    keyword = request.args.get("keyword", "").strip()
    if not keyword:
        return render_template("home.html", error="검색어를 입력해 주세요."), 400

    jobs_by_source, errors = search_jobs(keyword)
    return render_template(
        "home.html", keyword=keyword, jobs_by_source=jobs_by_source, errors=errors
    )


if __name__ == "__main__":
    app.run(debug=True)
