"""Pedal transitions for one SooperLooper loop; no audio or GUI dependencies."""
def transition(action,state,length):
 if state<0:return [],state,False
 empty=length<=0 or state==0
 if action=='record_play':
  if state in (2,3):return ['record'],4,True
  if state==5:return ['overdub'],4,True
  if empty:return ['record'],2,False
  return ['pause_off','mute_off','trigger'],4,False
 if action=='overdub':
  if state in (2,3):return ['overdub'],5,False
  if empty:return [],state,False
  if state==5:return ['overdub'],4,True
  return ['pause_off','mute_off','overdub'],5,False
 if action=='pause':
  if state in (2,3):return ['record','pause_on'],14,True
  if state==5:return ['overdub','pause_on'],14,True
  if empty:return [],state,False
  if state==14:return ['pause_off'],4,False
  return ['pause_on'],14,True
 if action=='clear':
  ending=['record'] if state in (2,3) else ['overdub'] if state==5 else []
  return ending+['pause_off','undo_all'],0,True
 return [],state,False
