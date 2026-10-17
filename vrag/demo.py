"""Public, immutable synthetic corpus. Never reads private state or calls providers."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(prefix='/api/demo')
TITLES = ['Workshop safety: prepare the bench', 'Camera framing and lighting', 'Find evidence in video']
TEXT = ['Clear the workbench and check equipment before starting.', 'Check the camera lighting and keep hands visible.']

def videos():
    return [dict(id=f'sample-{i+1}', title=t, duration=60, source_file='Synthetic sample corpus',
                 youtube_id=None, webpage_url=None, view_count=None, channel_position=i,
                 num_segments=2, thumb=f'/sample/thumb-{i+1}.jpg', video='/sample/video.mp4',
                 transcript_source='sample', transcript_engine='sample', sample=True) for i,t in enumerate(TITLES)]

def segments():
    return [dict(id=f'{v["id"]}_{i:03d}', video_id=v['id'],title=v['title'],idx=i,start=i*30,end=(i+1)*30,text=t,frame=v['thumb']) for v in videos() for i,t in enumerate(TEXT)]

@router.get('/videos')
def library(): return videos()

@router.get('/videos/{vid}')
def detail(vid: str):
    v=next((v for v in videos() if v['id']==vid),None)
    if not v: raise HTTPException(404,'Unknown sample video')
    segs=[s for s in segments() if s['video_id']==vid]
    return {**v,'segments':segs,'transcript':segs,'transcripts':{}}

@router.get('/stats')
def stats():
    return dict(model='Synthetic sample · lexical retrieval, no embeddings',sample=True,segments=6,videos=3,dims=[768],views=['text'],view_descriptions={'text':'Sample transcript keyword matching; not vector inference'},storage=[{'dim':768,'bytes_per_view':0}],total_duration_s=180,views_built={})

@router.get('/search')
def search(q: str=Query('',max_length=8000), k:int=Query(10,ge=1,le=50),video_id:str|None=None):
    words=set(q.lower().split())
    rows=[s for s in segments() if video_id is None or s['video_id']==video_id]
    rows.sort(key=lambda s:len(words & set((s['text']+' '+s['title']).lower().split())),reverse=True)
    return dict(query=q,view='text',dim=768,hits=[{**s,'rank':i+1,'score':len(words & set(s['text'].lower().split()))} for i,s in enumerate(rows[:k])],sample=True,timing={'embed_ms':0,'search_ms':0})

class Question(BaseModel):
    question: str
    k:int=4

@router.post('/ask')
def ask(body:Question):
    clips=search(body.question,max(1,min(body.k,6)))['hits']
    return dict(question=body.question,answer='Sample evidence extract (no model generated this answer): '+clips[0]['text']+' [1]',clips=clips,settings={'view':'text','dim':768,'k':len(clips),'use_video':False,'use_audio':False},usage={'prompt_tokens':0,'completion_tokens':0},usage_available=False,timing={'retrieve_s':0,'generate_s':0},created_at='2026-10-16T12:00:00Z',sample=True)

@router.get('/answers')
def history(): return []

@router.get('/compare')
def compare(q:str=''):
    return dict(query=q,view='text',k=6,columns=[{'dim':768,'hits':search(q,k=10)['hits'],'overlap_with_768':1,'top1_matches_768':True,'bytes_per_view':0}],sample=True)

@router.get('/compare-views')
def compare_views(q:str=''):
    return dict(query=q,dim=768,k=5,columns=[{'view':'text','hits':search(q,k=10)['hits']}],sample=True)

@router.get('/experiments')
def experiments():
    return dict(created_at='2026-10-16T12:00:00Z',model='Synthetic UI fixture · not a measured benchmark',sample=True,num_segments=6,num_queries=1,query_types={'spoken':1,'visual':0},query_embed_ms=0,dims=[768],views=['text'],storage=[{'dim':768,'bytes_per_vector':0,'bytes_per_view':0,'bytes_all_views':0}],grid=[{'view':'text','dim':768,'query_type':'all','recall@1':1,'recall@5':1,'recall@10':1,'mrr@10':1,'neighbor_recall@5':1,'video_hit@1':1,'n':1,'search_ms':0}],per_query=[{'query':'Prepare the bench','type':'spoken','segment_id':'sample-1_000','video_id':'sample-1','source':'synthetic fixture','ranks':{'text@768':1},'segment':search('bench',k=10)['hits'][0]}])
