import sys
import json
import ollama
from database.mongodb import db_manager
from config.settings import settings
from candidate_sheet import update_cv_result

db_manager.connect()
candidates = list(db_manager.candidates.find({}))
print(f'Processing {len(candidates)} candidates...')

for c in candidates:
    name = c.get('full_name', 'Unknown')
    cv   = c.get('raw_cv_text', '')

    if not cv or not cv.strip():
        print(f'  Skipping {name} - no CV text')
        continue

    print(f'  Extracting for {name}...')

    prompt = '''Read this CV and extract the following. Return ONLY valid JSON, nothing else.
{
  "education": "highest degree and institution in one line",
  "experience": "summary of work experience in one line",
  "skills": ["skill1", "skill2", "skill3"]
}

CV:
''' + cv[:3000]

    try:
        resp = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.1, 'num_predict': 300}
        )
        raw   = resp['message']['content']
        start = raw.find('{')
        end   = raw.rfind('}') + 1
        data  = json.loads(raw[start:end])

        education  = data.get('education', '')
        experience = data.get('experience', '')
        skills     = data.get('skills', [])
        skills_str = ', '.join(skills) if isinstance(skills, list) else str(skills)

        # Update MongoDB
        db_manager.candidates.update_one(
            {'_id': c['_id']},
            {'$set': {
                'education':        [education] if education else [],
                'work_experience':  [{'summary': experience}] if experience else [],
                'skills_extracted': skills if isinstance(skills, list) else [],
            }}
        )

        # Update Google Sheet
        shortlisted = c.get('status') not in ['not_selected', 'received', 'processing', 'scored']
        update_cv_result(
            c.get('email', ''),
            c.get('final_score') or 0,
            shortlisted,
            education=education,
            experience=experience,
            skills=skills_str,
            full_name=name
        )
        print(f'    Done: {education} | {skills_str[:60]}')

    except Exception as e:
        print(f'    Error for {name}: {e}')

print('\nAll done.')
db_manager.disconnect()
