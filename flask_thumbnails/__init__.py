import logging #DEBUG
import os, re
try:
    from PIL import Image, ImageOps
except ImportError:
    raise RuntimeError('Image module of PIL needs to be installed')

class Thumbnail(object):
    def __init__(self, app=None):
        if app is not None:
            self.init_app(app)
        else:
            self.app = None

    def init_app(self, app):
        self.app = app
        self._init_config(app.config)
        app.jinja_env.filters['thumbnail'] = self.thumbnail

    def thumbnail(self, img_url, size, crop=None, bg=None, quality=100):
        """

        :param img_url: url img - '/assets/media/summer.jpg'
        :param size: size return thumb - '100x100'
        :param crop: crop return thumb - 'fit' or None
        :param bg: tuple color or None - (255, 255, 255, 0)
        :param quality: JPEG quality 1-100
        :return: :thumb_url:
        """

        # builds unique thumbnail name out of all the options and returns it
        try:
            img_url = self._clean_slashes(img_url)
            thumb_url = self._build_thumbnail_url(img_url, size, crop, bg, quality)
            # check if we already have it in storage
            self._check_and_create(thumb_url, img_url, size, crop, bg, quality) # maybe ascyn
            return self.get_serve_url(thumb_url)
        except Exception as e:
            logging.error("flask.thumbnails: creating and using thumbnail for '{}' failed.\nError: {}".format(img_url,str(e)))
            return img_url # worst case it's not a thumbnail, still have to return the cleaned string (withouth slashes)

    def _check_and_create(self, thumb_url, img_path, size, crop, bg, quality):
        """ maybe asycn, but returns immediatly either case """
        if self._thumb_exists(thumb_url) is False:
            # get original image and transform to thumbail
            self._create_thumb(thumb_url, img_path, size, crop, bg, quality) # store thumbnail and return url
        return

    def get_serve_url(self, url):
        return url

    def _store_thumb(self, thumb_url, thumb_pic, quality=100):
        try:
            thumb_filepath = self._get_thumb_filepath(thumb_url)
            # set up thumbnail folders if not already there
            self._create_directory_for_path(thumb_filepath)
            thumb_pic.save(thumb_filepath,quality=quality)
        except IOError as e:
            # TODO: better:
            # raise
            raise Exception("flask.thumbnails: couldn't create thumbnail @ '{}'\nError: {}".format(thumb_filepath, str(e)))
        return thumb_url

    # check if thumbnail already exists
    def _thumb_exists(self, thumb_url):
        thumb_filepath = self._get_thumb_filepath(thumb_url)

        logging.debug('flask.thumbnail._thumb_exists: check path: "{}"'.format(thumb_filepath)) #DEBUG
        exists = os.path.exists(thumb_filepath)
        logging.debug('flask.thumbnail._thumb_exists: exist: "{}"'.format(str(exists))) #DEBUG
        return exists
    

    def _create_thumb(self, thumb_url, img_path, size, crop, bg, quality):
        orig_pic =  self._get_original_img(img_path) 
        thumb_img_data = self._build_thumb(orig_pic, size, crop, bg)
        self._store_thumb(thumb_url, thumb_img_data, quality)

    def _get_original_img(self, url):
        original_filename = self._build_original_img_filepath(url) # so it works properly on all os
        return self._open_image(original_filename) 

    @staticmethod
    def _create_directory_for_path(full_path):
        directory = os.path.dirname(full_path)

        #logging.debug('flask.thumbnail._create_directory_for_path: "%s":\ndirectory => "%s",',directory,full_path) #DEBUG

        # create folders
        try:
            if not os.path.exists(directory): #PATCH: if directory doesn't exist we create it, NOT if file doesn't exist.
                #logging.debug('flask.thumbnail._create_directory_for_path: "%s" DOESNT_EXISTS',directory) #DEBUG
                Thumbnail._create_directory_for_path(directory) # recursive directory creating
                os.makedirs(directory)
            return
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

    @staticmethod
    def _open_image(img_filepath):
        try:
            image = Image.open(img_filepath,"r") 
            #image = open(img_filepath,"rb")
        except IOError as e:
            logging.error('ERROR: flask.thumbnail._open_image: {}:\nerror:{}'.format(img_filepath, str(e)))
            raise e
        return image 


    def _build_thumbnail_url(self, img_url,*args):
        #try:
        url_dirname, img_name = os.path.split(img_url) # splits into dirname and basename e.g. 'link/to/','img.jpg'
        name, fm = os.path.splitext(img_name) # splits into filename and extension e.g. 'img','.jpg'

        # builds name for thumbnail out of all options so it's unique
        miniature = self._build_thumbnail_name(name, fm, *args)

#        thumb_url = os.path.join(self.app.config['MEDIA_THUMBNAIL_URL'], url_link, miniature) # Uses \\ on win
        #PATCH: We join a url, so don't us os.path, use standard / instead 
        # old for refactor: thumb_url = "/".join((self.app.config['MEDIA_THUMBNAIL_URL'], url_dirname, miniature))
        thumb_url = self._strip_starting_slash( self._strip_path(url_dirname, self.config['THUMB_ROOT_URL']) )
        thumb_url = "/".join((self.config['THUMB_NAIL_URL'], thumb_url, miniature))
        return thumb_url
        #except Exception as e:
        #    import sys
        #    exc_type, exc_obj, exc_tb = sys.exc_info()
        #    fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        #    logging.error("flask.thumbnailsGCS: blame: {}, {}: {}".format(exc_type, fname, exc_tb.tb_lineno))
        #    raise e

    def _build_thumb(self, orig_img_pic, size, crop, bg):
        # TODO: no quality has no effect e.g. img.save(thumb_filename, image.format, quality=quality)
        # calculate width and heights for thumbnail name
        width, height = [int(x) for x in size.split('x')]
        thumb_size = (width, height)

        if crop == 'fit':
            thumb_pic = ImageOps.fit(orig_img_pic, thumb_size, Image.ANTIALIAS)
        else:
            thumb_pic = orig_img_pic.copy()
            thumb_pic.thumbnail((width, height), Image.ANTIALIAS)

        if bg is not None:
            thumb_pic = self._bg_square(thumb_pic, bg)

        return thumb_pic

    @staticmethod
    def _bg_square(img, color=0xff):
        size = (max(img.size),) * 2
        layer = Image.new('L', size, color)
        layer.paste(img, tuple(map(lambda x: (x[0] - x[1]) / 2, zip(size, img.size))))
        return layer

    @staticmethod
    def _clean_slashes(url):
        return re.sub("/{2,}", "/", url) # replace two or more // with /

    @staticmethod
    def _strip_starting_slash(url):
        if '/' == url[0]: # check if path begins with /
            url = url[1:] # strips first / ==> need this because next steps joins with / and it would make // otherwise 
        return url
        
    @staticmethod
    def _strip_path(path,part=''):
        """ strips a path of part, 
            return: path, if part not found unharmed
            eg. works for following slash situation
            part/
            part
            THIS ONLY IF PATH ALSO STARTS WITH / 
            /part/
            /part
        """
        if '' == part : # if there is nothing to do because part is empty
            return path # go home

        #maybe alternative # re.sub(r"/*{}/*".format(part+"+"),"",path) # eg. part = 'static', path = 'static/img/frontpage-script.jpg'
        # old: # re.sub("/*"+part+"/*","",path)
        newpath = re.sub(r"/*{}/*".format(part+"+"),"",path,1) # regual exp: replaces everything /<part>/ at front, even '/<part>//' -- * means 0 or more
        return newpath
        #if path.startswith(part):
        #    return path[len(part):] # remove part

    @staticmethod
    def _build_thumbnail_name(name, fm, *args):
        for v in args:
            if v:
                name += '_%s' % v
        name += fm

        return name

    def _get_thumb_filepath(self, url):
        #removes inner part from path, so it fits again with the real place 
        return self._replace_path_with_url_for_item(self.config['THUMB_NAIL_PATH'], self.config['THUMB_NAIL_URL'], url) 

    def _get_full_thumburl(self, thumb_url):
        pass
        #return self._get_path_to_url_for_item(thumb_url,self.config['THUMB_ROOT_URL'], self.config['THUMB_ROOT_PATH']) 
        #return "/".join((self.config['THUMB_NAIL_URL'],thumb_url))

    def _build_original_img_filepath(self, url):
        return self._replace_path_with_url_for_item(self.config['THUMB_ROOT_PATH'], self.config['THUMB_ROOT_URL'], url) 

    def _replace_path_with_url_for_item(self, path, url, item):
        # strip item of <url> to replace, and strips of first /, because join doesn't work otherwise
        newpath = self._strip_starting_slash( self._strip_path(item, url) ) 
        return os.path.join(path, os.path.normpath(newpath)) # adds <path> in front, convert / to os.slashes first

    def _init_config(self,config):
        self.config = config
        self._refactor_old_config_names(config) # for compatibility sake also use deprecated config names
        # check need config, otherwise use default
        # todo: set to config.A
        self.config.setdefault('THUMB_ROOT_URL', '')
        self.config.setdefault('THUMB_NAIL_URL', self.config['THUMB_ROOT_URL']) # use same url then orignal image

        # check if all need configs are set
        self.config.setdefault('THUMB_ROOT_PATH','')

        if self.config.get('THUMB_NAIL_PATH', None) and not self.app.config.get('THUMB_NAIL_URL', None):
            raise RuntimeError('You\'re set THUMB_NAIL_PATH (or deprecated: MEDIA_THUMBNAIL_FOLDER) setting, so you also need to set THUMB_NAIL_URL (or deprecated: MEDIA_THUMBNAIL_URL) setting.')

        # if thumbnail folder is not set use same folder than original image
        self.config.setdefault('THUMB_NAIL_PATH', self.config['THUMB_ROOT_PATH'])

    def _refactor_old_config_names(self,config): 
        '''  for compatibility with original flask.thumbnail
             old => new
             MEDIA_URL => THUMB_ROOT_URL
             MEDIA_THUMBNAIL_URL => THUMB_NAIL_URL 
        '''
        try:
            config['THUMB_ROOT_URL'] = config['MEDIA_URL']
            config.pop('MEDIA_URL')
        except KeyError: # deprecated config format not used, we check new format later
            pass
        try:
            config['THUMB_NAIL_URL'] = config['MEDIA_THUMBNAIL_URL']
            config.pop('MEDIA_THUMBNAIL_URL')
        except KeyError: # deprecated config format not used, we check new format later
            pass
    pass