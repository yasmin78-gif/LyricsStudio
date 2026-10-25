"""Offline lyrics preparation and synchronization-data validation.

Approved FFmpeg ASR is implemented separately in whisper_local.py; this module
prepares references and validates data. Precise alignment still needs review.
This script NEVER downloads models, installs packages or accesses Resolve.
It does not infer speech, omissions or timecodes from the supplied reference.
"""
import argparse
from collections import Counter
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as source:
        for chunk in iter(lambda: source.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def frame_interval(start, end, fps):
    """Cover a valid interval, tolerating only binary noise at exact frames."""
    from lyrics_editor.timebase import frame_interval as convert
    return convert(start, end, fps)


def reference(original):
    tag=None
    result=[]
    for number,line in enumerate(original.splitlines(),1):
        if not line.strip():
            continue
        if re.fullmatch(r'\s*\[.*\]\s*',line):
            tag=line
            continue
        require('[' not in line and ']' not in line,'Inline/unbalanced tag needs manual review at line '+str(number))
        result.append(dict(id='REF-{:03d}'.format(len(result)+1),text=line,
                           original_line_number=number,original_tag=tag,
                           audible_status='not_assessed'))
    counts=Counter(x['text'] for x in result)
    for entry in result:
        entry['repeated_in_reference']=counts[entry['text']]>1
    return result


def validate(data):
    if data.get('schema_version')=='2.0':
        return validate_v2(data)
    require(data['schema_version']=='1.0','Unsupported schema version')
    require(data['fps']==24,'This schema version uses 24 FPS')
    ids=set()
    for row in data['occurrences']:
        require(row['id'] not in ids,'Duplicate occurrence ID')
        ids.add(row['id'])
        require(row['text'] and row['method']!='not_run','Recognized occurrence needs text and evidence method')
        require(row['reliability_status'] in ['automatic_unverified','needs_review','verified','rejected'],
                'Unknown reliability status')
        require(isinstance(row['reference_ids'],list),'Missing reference mapping')
        require(all(x in {r['id'] for r in data['reference_lines']} for x in row['reference_ids']),
                'Unknown reference ID')
        require(row['evidence'] and row['evidence']['source'],'Missing evidence source')
        start,end=row['start_time'],row['end_time']
        require((start is None)==(end is None),'Partial interval')
        if start is None:
            require(row['start_frame'] is None and row['end_frame'] is None and not row['display_enabled'],
                    'Untimed row cannot display')
        else:
            require(0<=start<end<=data['audio']['duration_seconds'],'Invalid measured time interval')
            a,b=frame_interval(start,end,data['fps'])
            require((a,b)==(row['start_frame'],row['end_frame']),'Inconsistent frame conversion')
        require(not row['display_enabled'] or
                (row['reliability_status']=='verified' and row['manual_reviewed'] and start is not None),
                'Only manually verified, timed occurrences may display')
        require(not row['display_enabled'] or row['granularity']=='lyric_line','ASR segments cannot become active lyric lines')
        require(row['reliability_status']!='rejected' or not row['display_enabled'],'Rejected row cannot display')
    require(data['status']!='blocked_missing_models' or not data['occurrences'],
            'Blocked result cannot claim recognized occurrences')
    require(data['status']!='ready_for_render' or all(r['reliability_status']=='verified' and r['manual_reviewed']
            for r in data['occurrences'] if r['display_enabled']),'Unreviewed render data')


def validate_v2(data):
    require(data['fps']==24,'Unsupported FPS')
    require(data['workflow_status'] in ['pilot_failed_no_full_alignment','needs_review','ready_for_render'],'Unknown workflow')
    reference=data['original_lyrics']['reference_lines']
    reference_ids={r['id'] for r in reference}
    require(len(reference_ids)==len(reference),'Duplicate original reference ID')
    require(data['original_lyrics']['evidence_role']=='reference_only_never_assumed_transcript','Original text cannot become acoustic evidence')
    recognized=data['recognized_occurrences']
    ids={r['id'] for r in recognized}
    require(len(ids)==len(recognized),'Duplicate ASR occurrence ID')
    require([r['sequence_index'] for r in recognized]==list(range(1,len(recognized)+1)),'Recognized order must be explicit and contiguous')
    def timing(t):
        require(t['status'] in ['unresolved','automatic_unverified','manual_confirmed'],'Unknown timing status')
        vals=[t[k] for k in ['start_time','end_time','start_frame','end_frame']]
        if t['status']=='unresolved':
            require(all(x is None for x in vals) and not t['manual_confirmation'] and not t['display_enabled'],
                    'Unresolved timing cannot contain active or accepted intervals')
        else:
            require(all(x is not None for x in vals),'Resolved timing needs all values')
            a,b=t['start_time'],t['end_time']
            require(0<=a<b<=data['audio']['duration_seconds'],'Invalid timing interval')
            require(frame_interval(a,b,data['fps'])==(t['start_frame'],t['end_frame']),'Frame conversion differs')
            require(t['method'],'Timed occurrence needs method')
            if t['status']=='automatic_unverified':
                require(not t['manual_confirmation'] and not t['display_enabled'],'Automatic timing cannot claim manual verification')
            else:require(t['manual_confirmation'],'Manual timing needs manual confirmation')
        require(not t['display_enabled'] or t['status']=='manual_confirmed','Only manually confirmed timing may display')
    for r in recognized:
        require(r['text'] and not r['manual_text_confirmation'],'ASR layer cannot claim manual text confirmation')
        require(r['wording_status'] in ['automatic_agreement','unresolved'],'Unknown wording status')
        require(set(r['reference_ids'])<=reference_ids,'Unknown reference mapping')
        require(r['hypothesis_repeat_of'] is None or r['hypothesis_repeat_of'] in ids,'Unknown repeat candidate')
        timing(r['timing'])
        require(not r['timing']['display_enabled'],'ASR layer stays inactive; promote manually reviewed content into confirmed layer')
        if r['alignment_status'] in ['pilot_rejected','excluded_unresolved_wording']:
            require(r['timing']['status']=='unresolved','Rejected/excluded alignment cannot become operational timing')
    confirmed=data['confirmed_occurrences']
    confirmed_ids={r['id'] for r in confirmed}
    require(len(confirmed_ids)==len(confirmed),'Duplicate confirmed occurrence ID')
    require([r['sequence_index'] for r in confirmed]==list(range(1,len(confirmed)+1)),'Confirmed order must be explicit')
    for r in confirmed:
        require(r['manual_text_confirmation'] and r['text'],'Confirmed layer requires manual wording confirmation')
        require(r['manual_evidence']['reviewer'] and r['manual_evidence']['source'],'Missing manual evidence')
        require(set(r['source_occurrence_ids'])<=ids,'Unknown ASR source')
        require(r['repeat_of'] is None or r['repeat_of'] in confirmed_ids,'Unknown confirmed repeat')
        timing(r['timing'])
    for attempt in data['alignment_attempts']:
        require(attempt['occurrence_id'] in ids,'Unknown attempted occurrence')
        require(not attempt['manual_confirmation'] and not attempt['display_enabled'],'Experiment cannot claim confirmation')
    if data['workflow_status']=='pilot_failed_no_full_alignment':
        require(not confirmed and all(r['timing']['status']=='unresolved' for r in recognized),'Failed pilot cannot yield accepted line times')


def schema():
    nullable_number={'type':['number','null'],'minimum':0}
    nullable_frame={'type':['integer','null'],'minimum':0}
    required=['id','text','start_time','end_time','start_frame','end_frame','section',
              'reliability_status','method','reference_ids','repeat_of','deviation_flags',
              'display_enabled','manual_reviewed','granularity','evidence']
    occurrence=dict(type='object',required=required,additionalProperties=False,properties=dict(
        id={'type':'string','minLength':1},text={'type':'string','minLength':1},
        start_time=nullable_number,end_time=nullable_number,start_frame=nullable_frame,end_frame=nullable_frame,
        section={'type':['string','null']},
        reliability_status={'enum':['automatic_unverified','needs_review','verified','rejected']},
        method={'enum':['asr','asr_plus_alignment','manual_listening']},
        reference_ids={'type':'array','items':{'type':'string'}},repeat_of={'type':['string','null']},
        deviation_flags={'type':'array','items':{'enum':['repeated','modified','additional','unclear']}},
        display_enabled={'type':'boolean'},manual_reviewed={'type':'boolean'},
        granularity={'enum':['lyric_line','asr_segment']},
        evidence={'type':'object','required':['source'],'properties':{'source':{'type':'string','minLength':1}},'additionalProperties':True}))
    reference_schema={'type':'object','required':['id','text','original_line_number','original_tag','audible_status','repeated_in_reference'],
                      'additionalProperties':False,'properties':dict(id={'type':'string'},text={'type':'string'},
                       original_line_number={'type':'integer','minimum':1},original_tag={'type':['string','null']},
                       audible_status={'enum':['not_assessed','matched','omitted','unclear']},
                       repeated_in_reference={'type':'boolean'})}
    return {'$schema':'https://json-schema.org/draft/2020-12/schema',
            'title':'Lyrics timing data 1.0','type':'object',
            'required':['schema_version','status','fps','audio','reference_lines','occurrences'],
            'properties':{'schema_version':{'const':'1.0'},'status':{'enum':['blocked_missing_models','needs_review','ready_for_render']},
                          'fps':{'const':24},'audio':{'type':'object','required':['sha256','duration_seconds'],
                           'properties':{'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},'duration_seconds':{'type':'number','exclusiveMinimum':0}}},
                          'reference_lines':{'type':'array','items':reference_schema},
                          'occurrences':{'type':'array','items':occurrence}},
            'allOf':[{'if':{'properties':{'status':{'const':'blocked_missing_models'}}},
                      'then':{'properties':{'occurrences':{'maxItems':0}}}}]}


def prepare(args):
    source=Path(args.original)
    analysis=json.loads(Path(args.analysis).read_text(encoding='utf-8'))
    require(sha(args.audio)==analysis['source']['sha256'],'Audio hash differs from existing analysis')
    text=source.read_text(encoding='utf-8')
    refs=reference(text)
    out=Path(args.output_directory)
    require(out.is_dir(),'Output directory must already exist')
    paths=[out/name for name in ['lyrics_clean.txt','lyrics_timing.json','lyrics_timing.schema.json']]
    require(not any(p.exists() for p in paths),'A target exists; no overwrite')
    data=dict(schema_version='1.0',status='blocked_missing_models',fps=24,
              audio=dict(path=str(Path(args.audio).resolve()),sha256=analysis['source']['sha256'],
                         duration_seconds=analysis['audio']['duration_seconds']),
              original=dict(path=str(source.resolve()),sha256=sha(source),source='Vollständiger vom Benutzer zuvor im Chat gelieferter Suno-Text'),
              reference_line_count=len(refs),reference_lines=refs,occurrences=[],
              recognized_line_count=None,recognized_count_status='not_measured',
              blocker='No suitable local ASR model weights found; no transcription/alignment run',
              interval_convention='seconds from audio start; [start,end); floor(start*24), ceil(end*24); end_frame exclusive',
              suno_tags_are_evidence=False)
    validate(data)
    with paths[0].open('x',encoding='utf-8',newline='\n') as f:
        f.write('\n'.join(x['text'] for x in refs)+'\n')
    for path,value in [(paths[1],data),(paths[2],schema())]:
        with path.open('x',encoding='utf-8') as f:
            json.dump(value,f,ensure_ascii=False,indent=2)
    # Confirm cleaning removed only whole tag lines and blanks, without editing lyric wording.
    require(paths[0].read_text(encoding='utf-8').splitlines()==[x['text'] for x in refs],'Reference mismatch')
    print('Prepared {} reference lines; no audible lines assessed; no time intervals assigned.'.format(len(refs)))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='mode',required=True)
    prep=sub.add_parser('prepare')
    prep.add_argument('--original',required=True)
    prep.add_argument('--analysis',required=True)
    prep.add_argument('--audio',required=True)
    prep.add_argument('--output-directory',required=True)
    valid=sub.add_parser('validate')
    valid.add_argument('input')
    args=parser.parse_args()
    if args.mode=='prepare':
        prepare(args)
    else:
        data=json.loads(Path(args.input).read_text(encoding='utf-8'))
        validate(data)
        print('Data validation passed; this does NOT verify audible lyrics or complete ASR.')


if __name__=='__main__':
    main()
