import importlib.util,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('films',str(Path(__file__).with_name('update_films.py')));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RecoveryTest(unittest.TestCase):
 def test_channel_duration_and_live_priority(self):
  sid,name,ch,minimum=m.EXTRA_SERIES[0];item=dict(id=sid);cfg={'sections':[{'id':'filma-shqip','items':[item]}]}
  entries=[dict(id='a',title=name+' Episodi 32'),dict(id='b',title=name+' Episodi 33'),dict(id='c',title=name+' Episodi 34')]
  meta=[dict(entries[0],channel_id=ch,duration=3600,live_status='is_live'),dict(entries[1],channel_id=ch,duration=3600),dict(entries[2],channel_id='wrong',duration=3600)]
  lookup={v['id']:v for v in meta}
  with patch.object(m,'list_channel',return_value=entries),patch.object(m,'_fetch_meta',side_effect=lambda url:lookup[url.split('=')[-1]]):
   self.assertTrue(m.update_extra(cfg,datetime.now(timezone.utc)))
  self.assertEqual('a',item['videoId']);self.assertEqual('',item['url']);self.assertEqual('live',item['state'])
 def test_filters(self):
  for sid,name,ch,minimum in m.EXTRA_SERIES:
   film=dict(id=sid,keywords=[name],exclude=['promo'])
   self.assertTrue(m.title_ok(name+' Episodi 20',film));self.assertFalse(m.title_ok(name+' Promo Episodi 21',film));self.assertFalse(m.episode_ok(dict(title=name+' Episodi 20',duration=60),film))
unittest.main()
