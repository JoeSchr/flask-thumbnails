from . import Thumbnail
import os, re
import StringIO
import logging #DEBUG
import PIL
from google.appengine.api import app_identity
from google.appengine.ext import blobstore
from google.appengine.api import urlfetch
import cloudstorage as gcs
import google.appengine.api.images as gimages

class ThumbnailGCS(Thumbnail):
    """makes Thumbnail work with GAE, extends flask.thumbnail"""
    _gs_bucket = None
    def __init__(self, app=None):
        super(self.__class__, self).__init__(app)
    
    def thumbnail(self, img_url, size, crop=None, bg=None, quality=100):
        """

        :param img_url: url img - '/assets/media/summer.jpg'
        :param size: size return thumb - '100x100'
        :param crop: crop return thumb - 'fit' or None
        :param bg: tuple color or None - (255, 255, 255, 0)
        :param quality: JPEG quality 1-100
        :return: :thumb_url:
        """
        '''
        #thumbnail_filter:        
          get blobstore_url from content gs/path/imagename.ext.url

          except NOT_EXIST:            
                get orig_image
                store orig_image at gs/path/imagename.ext
                get blobstore_url from gs_image.get_serving_url
                store blobstore_url @ gs/path/imagename.ext.url
       
           build_thumbnail_url(blogstore_url, options)
               # extends_url with option arguments for size and crop
            
           return thumbnail_url
        '''    
        # builds unique thumbnail name out of all the options and returns it
        try:
            img_url = self._clean_slashes(img_url)
            # thumb_url = /gs/path/filename.ext.bsurl=sXX-c? 
            try:
                thumb_url = self._build_thumbnail_url(img_url, size, crop, bg, quality)
                url = self.get_serve_url(thumb_url)
            except gcs.errors.NotFoundError as e:
                logging.debug("flask.thumbnailsGCS: no thumbnail for '{}' found, creating new".format(img_url))
                self._check_and_create(thumb_url, img_url, size, crop, bg, quality) # maybe ascyn
                url = self.get_serve_url(thumb_url)
            return url
        except Exception as e:
            logging.error("flask.thumbnailsGCS: creating and using thumbnail for '{}' failed.\nError: {}".format(img_url,str(e)))
            import sys, os
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error("flask.thumbnailsGCS: blame: {}, {}: {}".format(exc_type, fname, exc_tb.tb_lineno))
            return img_url # worst case it's not a thumbnail, still have to return the cleaned string (withouth slashes)


    def _store_thumb(self, thumb_url, thumb_pic, quality=100):
        try:
            thumb_filepath = self._gs_path(thumb_url)
            import mimetypes
            (content_type, content_encoding) = mimetypes.guess_type(thumb_url, strict=True)
            with gcs.open(thumb_filepath,
                                    'w',
                                    content_type=content_type,
                                    options={'x-goog-acl': 'public-read'}) as thumb_gcs:
                fileext=content_type.split("/")[-1]
                thumb_pic.save(thumb_gcs, fileext) # TODO save(thumb_gcs, fileext, QUALITY)
        except Exception as e:
            # TODO: better:
            # raise
            raise Exception("flask.thumbnailGAE._store_thumb: couldn't create thumbnail @ '{}'\nError: {}".format(thumb_url, str(e)))
        return thumb_filepath

    def _check_and_create(self, thumb_url, img_path, size, crop, bg, quality):
        """ makes async calls to create this thumbnails """
        sidecar_url = thumb_url.split("=s")[0]
        thumb_url = thumb_url.split(".bsurl")[0]
        thumb_pic = self._get_original_img(img_path) # dont have to transform image, gcs does that for use, so just simply store it
        gs_filepath = self._store_thumb(thumb_url, thumb_pic) # store in GCS

        # gs_serving_url: create once (slow), use forever (fast)
        blob_key = blobstore.create_gs_key("/gs" + gs_filepath)
        # get serving url and removes default size & crop modifiers
        serving_url =  gimages.get_serving_url(blob_key) 
        try:
        # delete old serving_url
            with gcs.open(gs_filepath+".bsurl", 'r') as sidecar:
                sidecar.readline() # throw away, is old serving url
                old_blob_key = sidecar.readline().rstrip("\n")
                gimages.delete_serving_url(old_blob_key)
        except gcs.errors.NotFoundError: #wasnt there
            pass
        # save serving_url in sidecare file /path/thumb.ext.bsurl
        with gcs.open(gs_filepath+".bsurl", 'w') as sidecar:
           sidecar.write(serving_url+"\n")
           sidecar.write(blob_key+"\n")
        return

    def get_serve_url(self, url):
        '''
        gets serving url corresponding from .bsurl file
        '''
        (bsurl,opt) = url.split("=s")
        gs_filepath = self._gs_path(bsurl)

        with gcs.open(gs_filepath, 'r') as f:
            serving_url = f.readline().rstrip('\n') # first line is serving url, second line is blobkey

        #DEBUG (local hack)
        if self.app.config["LOCAL"] is True:
            serving_url = serving_url.replace("0.0.0.0","localhost")
        return "{}=s{}".format(serving_url,opt)



    def _gs_path(self, url):
        if self._gs_bucket is None:
            self._gs_bucket = app_identity.get_default_gcs_bucket_name()
        gs_bucket = self._gs_bucket
        gs_path = "/" + gs_bucket + url
        return gs_path

    # call with size, crop, bg, quality
    def _build_thumbnail_url(self, img_url,*args):
        #calls our _build_thumbnail_name, also checks thumb and path url stuff
        return super(ThumbnailGCS, self)._build_thumbnail_url(img_url, *args)

    def _build_thumbnail_name(self, name, fm, *args):
        name += fm + ".bsurl="
        # have to do it this way because of backwards compatiblity
        for i, v in enumerate(args):            
            if 0 == i: #size
                size = v.split("x")[0] #removes last part from eg."100x100"
                name += "s{}".format(size)
            if 1 == i: # crop
                if "fit" == v:
                    name += "-c"
            if 1 < i:
                break; 

        return name

