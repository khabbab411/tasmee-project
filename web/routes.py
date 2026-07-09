@app.route("/submission/<int:submission_id>")
def submission(submission_id):
    if "teacher_id" not in session:
        return redirect(url_for("login"))
    s = get_submission_by_id(submission_id)
    if not s:
        return "التسميع غير موجود"
    return f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">

<head>
<meta charset="UTF-8">
<title>التسميع</title>

<style>

body{{font-family:Tahoma;background:#f5f5f5;padding:40px}}

.card{{
background:white;
padding:20px;
border-radius:10px;
max-width:700px;
margin:auto;
}}

textarea{{
width:100%;
height:180px;
margin-top:15px;
}}

button{{
padding:12px 25px;
margin-top:15px;
}}

</style>

</head>

<body>

<div class="card">

<h2>{s["name"]}</h2>

<p><b>النوع:</b> {s["submission_type"]}</p>

<p><b>الحالة:</b> {s["status"]}</p>

<p><b>الوقت:</b> {s["timestamp"]}</p>

<hr>

<p>الصوت:</p>
{"<audio controls style='width:100%'><source src='/voices/" + s["file_id"] + "' type='audio/ogg'></audio>" if s["file_id"] else "لا يوجد ملف صوتي"}

<hr>

<form>

<textarea placeholder="اكتب رد المعلمة هنا..."></textarea>

<br>

<button disabled>
إرسال الرد (سنفعله بالخطوة التالية)
</button>

</form>

</div>

</body>

</html>
"""
