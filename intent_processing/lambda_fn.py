from __future__ import print_function

import sys
sys.path.append("./lib")

from reduced_dotmap import DotMap

from intent_request_handlers import IntentRequestHandlers

import math

import datetime
import imp
import pytz
from dateutil.parser import *

import dre.actions as actions
from dre.whenDecision import *
from dre.decision import *
from dre.forecastCache import ForecastCache

import speech_config
import activities_config


class ConstructSpeechMixin(object):
    def say(self, title, output, reprompt_text, should_end_session=False):
        return {
            'version': '1.0',
            'sessionAttributes': {'slots': self.event.session.toDict()['slots']},
            'response': {
                'outputSpeech': {
                    'type': 'PlainText',
                    'text': output
                },
                'card': {
                    'type': 'Simple',
                    'title': 'SessionSpeechlet - ' + title,
                    'content': 'SessionSpeechlet - ' + output
                },
                'reprompt': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': reprompt_text
                    }
                },
                'shouldEndSession': should_end_session
            }
        }


class Session(IntentRequestHandlers, ConstructSpeechMixin):
    def __init__(self, event, context, cache=ForecastCache()):
        self._event = event
        self._context = context
        self._cache = cache

        self.event = DotMap(event)
        self.context = DotMap(context)

        original = self.event.request.intent.slots.values()
        combined = original[:]

        print('evt', self.event)
        try:
            for slot in self.event.session.attributes.slots:
                if slot in [ns.name for ns in original]:
                    if 'value' in self.event.session.attributes.slots[slot]:
                        # if value is not none, replace
                        for c in combined:
                            if c.name == slot:
                                combined[combined.index(c)] = self.event.session.attributes.slots[slot]
                    else:
                        pass # otherwise, ignore
                else:
                    combined.append(self.event.session.attributes.slots[slot])
        except AttributeError:
            pass

        self.event.session.slots = DotMap({c.name: c.toDict() for c in combined})

        self.slot_interactions = [SlotInteraction(self.event, s, self.event.session.slots.activity.value,
                                                self.event.session.user.userId) for s in self.event.session.slots.values()]

        config_slots = [{"name": "score"}, {"name": "conditions"}]
        self.slot_interactions.extend([SlotInteraction(self.event, DotMap(s), self.event.session.slots.activity.value,
                                                self.event.session.user.userId) for s in config_slots])

        self.greeting = speech_config.session.greeting
        self.reprompt = speech_config.session.reprompt
        self.sign_off = speech_config.session.sign_off
        self.help = speech_config.session.help

        IntentRequestHandlers.__init__(self)

    def respond(self):
        if self.event.request.type == "LaunchRequest":
            speech = self.greeting_speech
        elif self.event.request.type == "IntentRequest":
            if self._intent_request_map[self.event.request.intent.name]['grab_session']:
                self.current_intent = self.event.request.intent.name
            speech = self.attempt_intent()
        elif self.event.request.type == "SessionEndedRequest":
            speech = self.sign_off_speech

        return speech

    def attempt_intent(self):
        unset_sis = (si for si in self.slot_interactions if si.slot.value==None)
        try:
            this_unset_si = unset_sis.next()
            self._help = this_unset_si.help
            speech = this_unset_si.ask()
        except StopIteration:
            ir_handler = self._intent_request_map[self.event.request.intent.name]['function']
            # we might need to combine slot_interactions with other config
            # or else define some decent slot_interactions for pure config variables
            inputs = DotMap({i.slot.name: i.slot.value for i in self.slot_interactions})
            speech = ir_handler(inputs)

        return speech

    @property
    def greeting_speech(self):
        return self.say(title="Greeting",
                        output=self.greeting,
                        reprompt_text=self.reprompt)

    @property
    def sign_off_speech(self):
        return self.say(title="Sign Off",
                        output=self.sign_off,
                        reprompt_text="",
                        should_end_session=True)
        

class SlotInteraction(ConstructSpeechMixin):
    def __init__(self, event, slot, action_name, user_id):
        self.event = event
        self.slot = slot
        self.action_name = action_name
        self.user_id = user_id

        if not 'value' in slot or slot['value']==None:
            try:
                self.slot.value = activities_config.get_config(slot.name, action_name, user_id)
            except KeyError:
                self.slot.value = None

                self.title = speech_config.__dict__[self.slot.name].title
                self.question = speech_config.__dict__[self.slot.name].question
                self.reprompt = speech_config.__dict__[self.slot.name].reprompt
                self.help = speech_config.__dict__[self.slot.name].help

    def ask(self):
        return self.say(self.title, self.question, self.reprompt)


def go(event, context, cache=ForecastCache()):
    session = Session(event, context, cache)
    return session.respond()