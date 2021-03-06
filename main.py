from __future__ import print_function

import sys
reload(sys)
sys.setdefaultencoding('utf8')

import os

## Allow labels to have background colors
from LabelB import LabelB

import inspect

import time
import datetime
import requests, requests.utils

try:
    import cPickle as pickle
except ImportError:
    import pickle
#import urllib
#import base64
#import urllib2

import re

##from html2rest import html2rest
##import StringIO
from HTMLParser import HTMLParser
#from bs4 import BeautifulSoup

import webbrowser

import kivy

kivy.require('1.9.0')

## TODO:  integrate a config file
##from kivy.config import Config
from kivy.logger import Logger

from kivy.app import App
from kivy.lang import Builder
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.factory import Factory

from kivy.clock import Clock

from kivy.properties import ObjectProperty

from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition

from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView

from kivy.utils import escape_markup
from kivy.graphics import Color

from kivy.storage.jsonstore import JsonStore
from kivy.storage.dictstore import DictStore

def this_line():
    callerframerecord = inspect.stack()[1]
    ## 0 represents this line
    ## 1 represents line at caller
    frame = callerframerecord[0]
    info = inspect.getframeinfo(frame)
    return info.lineno

## We use a very strict regex pattern because of how we treat
## planlove as a special form of URL to be parsed
## read.php?searchname=gspelvin
planlove_re = re.compile( "^read\.php\?searchname=([a-zA-Z0-9]+)$" )
autofinger_level_re = re.compile( "^level_[0-9]$" )

## TODO - add a if( debug mode flag ): here?
##        or maybe make this a toggle on the home screen
##        to use an alternate backend
base_url = 'https://www.grinnellplans.com'

api_urls = { 'autofinger' : '{}/api/1/index.php?task={}'.format( base_url , 'autofingerlist' ) ,
             'read'       : '{}/api/1/index.php?task={}'.format( base_url , 'read' ) ,
             'login'      : '{}/api/1/index.php?task={}'.format( base_url , 'login' ) }

plan_name_parser = HTMLParser()

class PlansHTMLParser(HTMLParser):
    plan_buffer = ''
    
    def handle_starttag(self, tag, attrs):
        ## TODO:  add support for <hr>, <pre>
        ## https://www.grinnellplans.com/documents/faq.html#htmltags
        ## https://github.com/kivy/kivy/tree/master/kivy/data/fonts
        if( tag == 'a' ):
            href_content = None
            class_type = None
            for attr in attrs:
                if( attr[ 0 ] == 'href' ):
                    href_content = attr[ 1 ]
                elif( attr[ 0 ] == 'class' ):
                    class_type = attr[ 1 ]
            self.plan_buffer = ''.join( ( self.plan_buffer ,
                                          '[ref=' ,
                                          href_content ,
                                          ']' ) )
            if( class_type == 'planlove' ):
                ##print( '{} -> {}'.format( href_content ,
                ##                          planlove_re.findall(href_content)))
                ##planlove_target = planlove_re.findall( href_content )[ 0 ]
                self.plan_buffer = ''.join( ( self.plan_buffer ,
                                              '[color=' ,
                                              cookie_jar.get( 'default_color_scheme' )[ 'planlove_fg' ] ,
                                              ']' ) )
            elif( class_type == 'onplan' ):
                self.plan_buffer = ''.join( ( self.plan_buffer ,
                                              '[color=' ,
                                              cookie_jar.get( 'default_color_scheme' )[ 'link_fg' ] ,
                                              ']' ) )
        elif( tag == 'pre' ):
            ## TODO:  Make mono font configurable
            mono_font = 'RobotoMono-Regular'
            self.plan_buffer = ''.join( ( self.plan_buffer ,
                                          '[font=' ,
                                          mono_font ,
                                          ']' ) )
        elif( tag == 'b' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[b]' ) )
        elif( tag == 'i' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[i]' ) )
        elif( tag == 'u' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[u]' ) )
        elif( tag == 'strike' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[s]' ) )

        
    def handle_endtag(self, tag):
        if( tag == 'a' ):
            ## TODO: deal with nested tags
            self.plan_buffer = ''.join( ( self.plan_buffer ,
                                          '[/color][/ref]' ) )
        elif( tag == 'pre' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[/font]' ) )
        elif( tag == 'b' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[/b]' ) )
        elif( tag == 'i' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[/i]' ) )
        elif( tag == 'u' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[/u]' ) )
        elif( tag == 'strike' ):
            self.plan_buffer = ''.join( ( self.plan_buffer , '[/s]' ) )
        
    def handle_data(self, data):
        self.plan_buffer = ''.join( ( self.plan_buffer ,
                                      escape_markup( data ) ) )

from kivy.utils import platform

## Hack until this bug is fixed to launch native Android browser
## https://github.com/kivy/python-for-android/issues/846
## http://python-for-android.readthedocs.io/en/latest/apis/#using-android
## TODO:  reorganize to preload to that the first URL isn't so slow
def launch_webbrowser(url):
    if platform == 'android':
        from jnius import autoclass, cast
        def open_url(url):
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            activity = PythonActivity.mActivity
            Intent = autoclass('android.content.Intent')
            Uri = autoclass('android.net.Uri')
            browserIntent = Intent()
            browserIntent.setAction(Intent.ACTION_VIEW)
            browserIntent.setData(Uri.parse(url))
            currentActivity = cast('android.app.Activity', activity)
            currentActivity.startActivity(browserIntent)
            
        # Web browser support.
        class AndroidBrowser(object):
            def open(self, url, new=0, autoraise=True):
                open_url(url)
            def open_new(self, url):
                open_url(url)
            def open_new_tab(self, url):
                open_url(url)
                
        webbrowser.register('android', AndroidBrowser, None, -1)
        
    webbrowser.open(url)
## END hack
        
cookie_jar = DictStore( 'cookies.dat' )
session = None

autofinger_list = {}

now_time = datetime.datetime.now()
now_stamp = now_time.strftime( "%Y-%m-%d %H:%M:%S" )
now_filesafe = now_time.strftime( "%Y-%m-%d_%H%M%S" )
log_file = 'grinnell_plans_{}.txt'.format( now_filesafe )

## TODO:  add remember username/password button
def LLOOGG( message ):
    global now_stamp
    global log_file
    Logger.info( message )
    log_file = os.path.join( App.get_running_app().user_data_dir ,
                             'log' ,
                             log_file )
    with open( log_file , 'a' ) as fp:
        fp.write( '{}\t{}\n'.format( now_stamp , message ) )

########################################################################
##
########################################################################

def get_json_list( session , username = None , testing = False ):
    if( username == None ):
        try:
            username = cookie_jar.get( 'user_name' )[ 'username' ]
        except Exception as e:
            st = datetime.datetime.fromtimestamp( time.time() ).strftime('%Y-%m-%d %H:%M:%S')
            LLOOGG( 'Error:  Unable to extract username from cookie jar - {1}\n'.format( st , e ) )
            return None
    ##
    try:
        url = api_urls[ 'autofinger' ]
        response = session.post( url ,
                                 data = { 'username' : username } )
        if( testing ):
            LLOOGG( 'Staging: Status Code = {}'.format( response.status_code ) )
        if( response.status_code == 200 ):
            json_response = response.json()
            response.close()
            json_message = json_response[ 'message' ]
            json_success = json_response[ 'success' ]
            if( testing ):
                LLOOGG( 'Staging: JSON Response = {}'.format( json_response ) )
                LLOOGG( 'Staging: JSON Success = {}'.format( json_success ) )
                LLOOGG( 'Staging: JSON Message = {}'.format( json_message ) )
            if( json_success ):
                json_list = json_response[ 'autofingerList' ]
                return json_list
            else:
                return None
        else:
            ## Don't forget to close the response for good housekeeping
            response.close()
            return None
    except Exception as e:
        st = datetime.datetime.fromtimestamp( time.time() ).strftime('%Y-%m-%d %H:%M:%S')
        LLOOGG( 'Error: {1}'.format( st , e ) )
    return None


def session_login( session , username , password , testing = False ):
    try:
        if( username == '' ):
            LLOOGG( 'Error: Username must not be empty.' )
            return( False , session )
        elif( password == '' ):
            LLOOGG( 'Error: Password must not be empty.' )
            return( False , session )
        LLOOGG( "Staging: {} - {}".format( this_line() , api_urls[ 'login' ] ) )
        session = requests.Session()
        LLOOGG( "Staging: {} - {}".format( this_line() , 'session created' ) )
        response = session.post( api_urls[ 'login' ] ,
                                 data = { 'username' : username ,
                                          'password' : password } )
        LLOOGG( "Staging: {} - {}".format( this_line() , 'response generated' ) )
        if( testing ):
            LLOOGG( '{}'.format( response ) )
            LLOOGG( 'Staging: Status Code = {}'.format( response.status_code ) )
            LLOOGG( 'Headers = {}'.format( response.headers ) )
            LLOOGG( 'Text = {}'.format( response.text ) )
        if( response.status_code == requests.codes.ok ):
            ##
            json_response = response.json()
            response.close()
            json_success = json_response[ 'success' ]
            json_message = json_response[ 'message' ]
            if( testing ):
                LLOOGG( 'Staging: JSON Success = {}'.format( json_success ) )
                LLOOGG( 'Staging: JSON Message = {}'.format( json_message ) )
            if( json_success ):
                if( testing ):
                    print( '{} - {}'.format( this_line() , json_response ) )
                ## TODO - remember the SessionID cookie?
                #jar = response.cookies
                ##LLOOGG( '{}'.format( jar[ 'Cookie PHPSESSID' ] ) )
                if( testing ):
                    LLOOGG( '{}'.format( jar ) )
                ## TODO - if remember username is checked, then...
                cookie_jar.put( 'user_name' ,
                                username = username )
                ## TODO - if remember password is checked, then...
                ##cookie_jar.put( 'user_pass' ,
                ##                passwd = password )
                LLOOGG( 'Staging: {} - Logged in.  Checking plan...'.format( this_line() ) )
                with open('session.dat', 'w') as fp:
                    pickle.dump( requests.utils.dict_from_cookiejar( session.cookies ) ,
                                 fp )
                return( True , session )
            else:
                LLOOGG( 'Warning: ' +
                        'Unsuccessful login. Returning to login page:  {}'.format( json_message ) )
                return( False , session )
        else:
            LLOOGG( 'Error: Failed to log in (Status Code = {})'.format( response.status_code ) )
            return( False , session )
    except Exception as e:
        st = datetime.datetime.fromtimestamp( time.time() ).strftime('%Y-%m-%d %H:%M:%S')
        LLOOGG( 'Error:  {1}\n'.format( st , e ) )
    return( False , session )


########################################################################
##
########################################################################

class LoginScreen( Screen ):
    __version__ = "18.38.1"

    def version( self , *args ):
        return self.__version__

    def update_autofinger( self , json_list = None ):
        global session
        ## Updating the autofinger list happens automatically by a new
        ## api call unless you provide a json_list of the autofinger
        ## level entries when calling this function.
        if( json_list == None ):
            json_list = get_json_list( session = session )
            if( json_list == None ):
                LLOOGG( 'Error: autofinger list still empty after trying to load it.' )
                return()
        ## Clear out the old global variable for update
        global autofinger_list
        autofinger_list = {}
        ## Loop through the autofinger levels to update each level in turn
        for level in json_list:
            level_number = level[ u'level' ]
            ##print( 'Level {}'.format( level_number ) )
            autofinger_list[ 'level_{}'.format( level_number ) ] = []
            ##autofinger_list[ 'level_{}'.format( level_number ) ] = ''
            level_string = 'level_{}'.format( level_number )
            for username in level[ u'usernames' ]:
                autofinger_list[ level_string ].append( username )
                ##print( "\t{}".format( username ) )


    def guestAuth( self , username , password ):
        pass


    def loadSavedSession( self ):
        global session
        if( os.path.exists( 'session.dat' ) ):
            with open('session.dat') as fp:
                tmp_cookies = requests.utils.cookiejar_from_dict( pickle.load( fp ) )
                session = requests.Session()
                session.cookies.update( tmp_cookies )
                plans_app.screens[ 0 ].ids.username.text = cookie_jar.get( 'user_name' )[ 'username' ]
            return True
        return False

    
    def endSession( self ):
        ## TODO - add a button to the home screen to that you can do very early
        ##        in case the saved data is corrupted somehow? same for cookie_jar, defaults?
        global session
        session = None
        if( os.path.exists( 'session.dat' ) ):
            os.remove( 'session.dat' )
        if( cookie_jar.exists( 'user_name' ) ):
            ## TODO:  make this a robust look-up rather than hard-coded index
            plans_app.screens[ 0 ].ids.username.text = cookie_jar.get( 'user_name' )[ 'username' ]
        plans_app.current = 'login'

    
    def logInTask( self , username , password ):
        plans_app.current = 'landing_page'
        global session
        LLOOGG( "Staging: {} - {}h {}w".format( this_line() ,
                                                plans_app.height ,
                                                plans_app.width ) )
        try:
            ( successful_login , session ) = \
              session_login( session , username , password )
            ##
            if( successful_login ):
                ## TODO - move this extra call to get_json_list back inside
                ##        the call to session_login
                json_list = get_json_list( session = session ,
                                           username = username )
                if( json_list == None ):
                    LLOOGG( 'Warning: I had trouble loading the autofinger list' )
                    plans_app.current = 'login_page'
                    self.endSession()
                    return()
                else:
                    self.update_autofinger( json_list )
            else:
                self.endSession()
                return()
        except Exception as e:
            st = datetime.datetime.fromtimestamp( time.time() ).strftime('%Y-%m-%d %H:%M:%S')
            LLOOGG( 'Error:  {1}\n'.format( st , e ) )
    

    def __init__(self , **kwargs ):
        super(LoginScreen, self).__init__(**kwargs)
        ## Setting color scheme
        #bg = cookie_jar.get( 'color_scheme' )[ 'background' ]
        with self.canvas.before:
            ## TODO - pull color from cookie_jar
            Color( 1 , 1 , 1 , 1 )
        Clock.schedule_once(self.init_ui, 0)
    
    def init_ui( self , dt = 0 ):
        ## Setting color scheme
        for this_child in self.children:
            for widget in this_child.walk( restrict = False ):
                if( type( widget ) == type( Button() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'button_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'button_fg' ]
                elif( type( widget ) == type( Label() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'label_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'label_fg' ]


class LoadingPage( Screen ):

    def on_enter( self ):
        pass

    
    def __init__(self , **kwargs ):
        super(LoadingPage, self).__init__(**kwargs)
        ## Setting color scheme
        #bg = cookie_jar.get( 'color_scheme' )[ 'background' ]
        with self.canvas.before:
            ## TODO - pull color from cookie_jar
            Color( 1 , 1 , 1 , 1 )
        Clock.schedule_once(self.init_ui, 0)
    
    def init_ui( self , dt = 0 ):
        ## Setting color scheme
        for this_child in self.children:
            for widget in this_child.walk( restrict = False ):
                if( type( widget ) == type( Button() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'button_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'button_fg' ]
                elif( type( widget ) == type( Label() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'label_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'label_fg' ]


class LandingPage( Screen ):
    ## TODO:  random buttons for each person on your autoread list
    ## https://kivy.org/docs/api-kivy.uix.floatlayout.html#module-kivy.uix.floatlayout
    ## TODO:  add refresh button or pull at top to refresh

    progress_bar = ObjectProperty()

    def load_autofinger_levels( self ):
        self.pop()
        global autofinger_list
        button_width = 0.9 * plans_app.width / 3
        button_height = plans_app.height * 0.5
        ##
        for level_name in plans_app.screens[ 2 ].ids:
            level_matches = autofinger_level_re.findall( level_name )
            if( len( level_matches ) == 0 ):
                ## Ignore widgets that aren't named "level_[0-9]"
                continue
            ##print( "\t{}".format( level_name ) )
            plans_app.screens[ 2 ].ids[ level_name ].clear_widgets()
            ## TODO:  reformat
            pretty_level_name = level_name[:1].upper() + \
                                level_name[1:].replace( '_' , ' ' )
            level_lbl = Label( id = '{}_lbl'.format( level_name ) ,
                               size_y = button_height ,
                               text = pretty_level_name ,
                               background_color = cookie_jar.get( 'color_scheme' )[ 'label_bg' ] ,
                               color = cookie_jar.get( 'color_scheme' )[ 'label_fg' ] )
            plans_app.screens[ 2 ].ids[ level_name ].add_widget( level_lbl )
            ## TODO:  is this line really necessary?
            plans_app.screens[ 2 ].ids[ level_name ].bind( minimum_height = plans_app.screens[ 2 ].ids[ level_name ].setter( 'height' ) )
            if( autofinger_list.has_key( level_name ) ):
                usernames_this_level = autofinger_list[ level_name ]
                level_progress_inc = len( usernames_this_level ) / 30
                for username in usernames_this_level:
                    ##print( "\t\t{}".format( username ) )
                    finger_btn = Button( text = username ,
                                         size_x = button_width ,
                                         size_y = button_height ,
                                         size_hint_y = None ,
                                         background_color = cookie_jar.get( 'color_scheme' )[ 'button_bg' ] ,
                                         color = cookie_jar.get( 'color_scheme' )[ 'button_fg' ] )
                    ##TODO:  bind readTask to this button
                    finger_btn.bind( on_press = plans_app.screens[ 3 ].readFromLevels )
                    plans_app.screens[ 2 ].ids[ level_name ].add_widget( finger_btn )
                    self.progress_bar.value += level_progress_inc
            else:
                self.progress_bar.value += 33
        self.progress_bar.value = 100
        
        
    def on_enter( self ):
        plans_app.screens[ 0 ].update_autofinger()
        self.load_autofinger_levels()
    
    
    def __init__(self , **kwargs ):
        super(LandingPage, self).__init__(**kwargs)
        ## Setting color scheme
        #bg = cookie_jar.get( 'color_scheme' )[ 'background' ]
        with self.canvas.before:
            ## TODO - pull color from cookie_jar
            Color( 1 , 1 , 1 , 1 )
        ## Pop-up + Progress Bar
        ## - https://gist.github.com/jsidew/4959534#file-kivy_progressbar_example-py
        self.progress_bar = ProgressBar()
        self.popup = Popup(
            title = 'Loading autofinger list...' ,
            content = self.progress_bar ,
            size_hint = ( 0.4 , 0.2 )
        )
        self.popup.bind(on_open=self.puopen)
        Clock.schedule_once(self.init_ui, 0)
    
    def init_ui( self , dt = 0 ):
        ## Setting color scheme
        for this_child in self.children:
            for widget in this_child.walk( restrict = False ):
                if( type( widget ) == type( Button() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'button_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'button_fg' ]
                elif( type( widget ) == type( Label() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'label_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'label_fg' ]

    def pop( self ):
        self.progress_bar.value = 1
        self.popup.open()
        
    def next(self, dt):
        if self.progress_bar.value >= 100:
            self.popup.dismiss()
            return False
        
    def puopen(self, instance):
        Clock.schedule_interval(self.next, 1/25)


class ReadPlan( Screen ):
    ## TODO:  add a button to flag plan for comment/later and see all flagged

    chunk_labels = []
    tag_start_stack = []
    tag_end_stack = []
        
    def on_enter( self ):
        pass
    
    def guestAuth( self , username ):
        ##print( '{} -|'.format( username ) )
        pass
    
    
    def cleanPlanBody( self , plan_body , this_encoding = None ):
        ##print( '{} - Cleaning plan body'.format( this_line() ) )
        plans_parser = PlansHTMLParser()
        if( this_encoding == None ):
            plans_parser.feed( plan_body )
        else:
            plans_parser.feed( plan_body.encode( this_encoding ) )
        return plans_parser.plan_buffer
        ## TODO: maybe replace beatufil soup with HTMLParser
        ## https://docs.python.org/2/library/htmlparser.html
        #if( this_encoding == None ):
        #    soup = BeautifulSoup( plan_body ,
        #                          'html.parser' )
        #else:
        #    soup = BeautifulSoup( plan_body.decode( this_encoding ) ,
        #                          'html.parser' )
        #return soup.get_text()
        if( this_encoding == None ):
            return plan_body
        ## Default
        return plan_body.encode( this_encoding )
    
    
    def cleanPlanName( self , plan_name , this_encoding ):
        ##return html_parser.unescape( plan_name.encode( this_encoding ) )
        return plan_name_parser.unescape( plan_name )

    
    ## TODO:  convert times to local timezone
    ## TODO:  add local vs. UTC vs. other timezone display options
    def adjustClock( self , timestamp ):
        return timestamp
    

    def readFromHomeButton( self ):
        username = plans_app.screens[ 0 ].ids.username.text
        if( username != '' ):
            self.readTask( username )
    
            
    def readFromFingerButton( self ):
        username = plans_app.screens[ 3 ].ids.finger.text
        if( username != '' ):
            self.readTask( username )

    
    def readFromLevels( self , button_instance ):
        username = button_instance.text
        if( username != '' ):
            self.readTask( username )

    
    def readFromRef( self , instance , ref_string ):
        planlove_matches = planlove_re.findall( ref_string )
        if( len( planlove_matches ) == 0 ):
            LLOOGG( 'readFromRef:  {} - generic url = {}'.format( this_line() , ref_string ) )
            launch_webbrowser( ref_string )
        else:
            username = planlove_matches[ 0 ]
            LLOOGG( 'readFromRef:  {} - {} from {}'.format( this_line() , username , ref_string ) )
            self.readTask( username )

    def extract_open_tags( self , text ):
        s = re.split( '(\[.*?\])' , text )
        s = [ x for x in s if x != '' ]
        for chunk in s:
            if( chunk.startswith( '[/' ) and
                chunk.endswith( ']' ) ):
                self.tag_start_stack.pop()
                self.tag_end_stack.pop()
            elif( chunk.startswith( '[' ) and
                chunk.endswith( ']' ) ):
                self.tag_start_stack.append( chunk )
                if( chunk.startswith( '[anchor' ) ):
                    ## TODO - treat closing anchors as special
                    self.tag_end_stack.append( '[/anchor]' )
                elif( chunk.startswith( '[color' ) ):
                    self.tag_end_stack.append( '[/color]' )
                elif( chunk.startswith( '[font' ) ):
                    self.tag_end_stack.append( '[/font]' )
                elif( chunk.startswith( '[ref' ) ):
                    ## TODO - treat closing ref as special
                    self.tag_end_stack.append( '[/ref]' )
                elif( chunk.startswith( '[size' ) ):
                    self.tag_end_stack.append( '[/size]' )
                else:
                    self.tag_end_stack.append( '{}/{}'.format( chunk[ 0 ] ,
                                                               chunk[ 1: ] ) )

    def redraw_label( self , instance , value ):
        instance.text_size = ( instance.width, None )
        instance.height = instance.texture_size[1]

    
    def plan_content_template( self , content = 'Hello World&br;' ):
        ## TODO - use a separate color pair for the plan content labels
        tmp_label = LabelB( color = cookie_jar.get( 'color_scheme' )[ 'content_fg' ] ,
                            bcolor = cookie_jar.get( 'color_scheme' )[ 'background' ] ,
                            halign = 'left' ,
                            valign = 'top' ,
                            markup = True ,
                            text = content )
        tmp_label.size_hint_y = None
        tmp_label.text_size = ( tmp_label.width , None )
        tmp_label.height = tmp_label.texture_size[ 1 ]
        tmp_label.bind( size = self.redraw_label ,
                        texture_size = self.redraw_label )
        ## TODO:  add on_long_press send to clipboard
        tmp_label.bind( on_ref_press = self.readFromRef )
        tmp_label.texture_update()
        return( tmp_label )

    def find_safe_ends( self , chunks , start , end ):
        if( end - start == 0 ):
            return None
        chunk = '\n'.join( chunks[ start : end ] )
        chunk_label = self.plan_content_template( chunk )
        ##TODO -
        ##from kivy.core.window import Window
        ##print( 'Window.size = {}\ntexture_size[1] = {}'.format( Window.height ,
        ##                                                        chunk_label.texture_size[ 1 ] ) )
        if( chunk_label.texture_size[ 1 ] < 30000 ):
            return( [ end ] )
        else:
            gap = int( ( end - start ) / 2 )
            return( self.find_safe_ends( chunks , start , start + gap ) + self.find_safe_ends( chunks , start + gap , end ) )
        
    def readTask( self , username ):
        global session
        for chunk_label in self.chunk_labels:
            self.ids.plan_grid.remove_widget( chunk_label )
        self.chunk_labels = []
        plans_app.current = 'read_plan'
        try:
            url = api_urls[ 'read' ]
            response = session.post( url ,
                                     data = { 'username' : username } )
            json_response = None
            if( response.status_code == requests.codes.ok ):
                json_response = response.json()
                ##print( 'Encoding = {}'.format( response.encoding ) )
                ##plan_body = response.text.encode( response.encoding )
                #### We don't actually need the grab the username because
                #### it was passed to the original function
                ##username = json_response[ 'plandata' ][ 'username' ]
                plan_body = self.cleanPlanBody( json_response[ 'plandata' ][ 'plan' ] ,
                                                response.encoding )
                plan_name = self.cleanPlanName( json_response[ 'plandata' ][ 'pseudo' ] ,
                                                response.encoding )
                last_login = self.adjustClock( json_response[ 'plandata' ][ 'last_login' ] )
                last_updated = self.adjustClock( json_response[ 'plandata' ][ 'last_updated' ] )
                response.close()
                plans_app.screens[ 3 ].ids.username.text = username
                plans_app.screens[ 3 ].ids.psuedo.text = plan_name
                plans_app.screens[ 3 ].ids.last_login.text = last_login
                plans_app.screens[ 3 ].ids.last_updated.text = last_updated
                plan_chunks = plan_body.splitlines()
                safe_chunk_ends = self.find_safe_ends( plan_chunks , 0 , len( plan_chunks ) )
                chunk_start = 0
                for chunk_end in safe_chunk_ends:
                    chunk = '\n'.join( plan_chunks[ chunk_start : chunk_end ] )
                    if( chunk == "" ):
                        chunk = " "
                    chunk_prefix = ''
                    for tag in reversed( self.tag_start_stack ):
                        chunk_prefix  = '{}{}'.format( tag ,
                                                       chunk_prefix )
                    self.extract_open_tags( chunk )
                    chunk_suffix = ''
                    for tag in reversed( self.tag_end_stack ):
                        chunk_suffix = '{}{}'.format( chunk_suffix ,
                                                      tag )
                    chunk = '{}{}{}'.format( chunk_prefix ,
                                             chunk ,
                                             chunk_suffix )
                    chunk_label = self.plan_content_template( chunk )
                    self.ids.plan_grid.add_widget( chunk_label )
                    self.chunk_labels.append( chunk_label )
                ##
                ## If we got here from clicking the read button, then empty out the data
                plans_app.screens[ 3 ].ids.finger.text = ''
                ## and move the scrollview back to the top of the page
                plans_app.screens[ 3 ].ids.content_scroller.scroll_to( plans_app.screens[ 3 ].ids.username )
        except Exception as e:
            st = datetime.datetime.fromtimestamp( time.time() ).strftime('%Y-%m-%d %H:%M:%S')
            LLOOGG( 'Error:  {1}\n'.format( st , e ) )

    def __init__(self , **kwargs ):
        super(ReadPlan, self).__init__(**kwargs)
        ## Setting color scheme
        #bg = cookie_jar.get( 'color_scheme' )[ 'background' ]
        #with self.canvas.before:
        #    ## TODO - pull color from cookie_jar
        #    Color( 1 , 1 , 1 , 1 )
        Clock.schedule_once(self.init_ui, 0)
    
    def init_ui( self , dt = 0 ):
        ## Setting color scheme
        for this_child in self.children:
            for widget in this_child.walk( restrict = False ):
                if( type( widget ) == type( Button() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'button_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'button_fg' ]
                elif( type( widget ) == type( Label() ) or
                      type( widget ) == type( LabelB() ) ):
                    widget.background_color = cookie_jar.get( 'color_scheme' )[ 'label_bg' ]
                    widget.color = cookie_jar.get( 'color_scheme' )[ 'label_fg' ]
        

class EditPlan( Screen ):
    pass

class ScreenManagement( ScreenManager ):
    pass
            

plans_app = Builder.load_file( "main.kv" )

class GrinnellPlansApp(App):

    def initilize_global_dirs(self):
        log_dir = os.path.join( App.get_running_app().user_data_dir , 'log' )
        if( not os.path.exists( log_dir ) ):
            os.makedirs( log_dir )

    def loadDefaultColorScheme( self ):
        ##if( not cookie_jar.exists( 'default_color_scheme' ) ):
        cookie_jar.put( 'default_color_scheme' ,
                        background = [ 1 , 1 , 1 , 1 ] ,
                        ## rgb(149,165,166)
                        button_bg = [ .58431372549019607843 , .64705882352941176470 , .65098039215686274509 , 1 ] ,
                        button_fg = [ 1 , 1 , 1 , 1 ] ,
                        label_bg = [ 0.5 , 0.5 , 0.5 , 1 ] ,
                        label_fg = [ 0 , 0 , 0 , 1 ] ,
                        content_fg = [ 0 , 0 , 0 , 1 ] ,
                        planlove_fg = '0000ff' ,
                        link_fg = '0000ff' )
    
    
    def loadColorScheme( self ):
        self.loadDefaultColorScheme()
        cookie_jar.put( 'color_scheme' ,
                        background = cookie_jar.get( 'default_color_scheme' )[ 'background' ] ,
                        button_bg = cookie_jar.get( 'default_color_scheme' )[ 'button_bg' ] ,
                        button_fg = cookie_jar.get( 'default_color_scheme' )[ 'button_fg' ] ,
                        label_bg = cookie_jar.get( 'default_color_scheme' )[ 'label_bg' ] ,
                        label_fg = cookie_jar.get( 'default_color_scheme' )[ 'label_fg' ] ,
                        content_fg = cookie_jar.get( 'default_color_scheme' )[ 'content_fg' ] ,
                        planlove_fg = cookie_jar.get( 'default_color_scheme' )[ 'planlove_fg' ] ,
                        link_fg = cookie_jar.get( 'default_color_scheme' )[ 'link_fg' ] )
    
    
    def build(self):
        ##print( 'Screens:  {}'.format( plans_app.screens ) )
        self.initilize_global_dirs()
        self.loadColorScheme()
        if( plans_app.screens[ 0 ].loadSavedSession() ):
            plans_app.current = 'landing_page'
        else:
            if( cookie_jar.exists( 'user_name' ) ):
                ## TODO:  make this a robust look-up rather than hard-coded index
                plans_app.screens[ 0 ].ids.username.text = cookie_jar.get( 'user_name' )[ 'username' ]
            plans_app.current = 'login'
        ##plans_app.current = 'landing_page'
        ##plans_app.current = 'loading_page'
        ##plans_app.current = 'read_plan'
        return plans_app


if __name__ == '__main__':
    GrinnellPlansApp().run()
    
