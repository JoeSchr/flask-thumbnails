from . import Thumbnail
import os, re
import StringIO
import logging #DEBUG
from google.appengine.api import app_identity
from google.appengine.ext import blobstore
from google.appengine.api import urlfetch
import cloudstorage as gcs
import google.appengine.api.images as gimages

def post_data(url, payload):
    import json
    import requests
    data = json.dumps(payload)
    headers={ "content-type":"application/json"
              , "datatype":"json"
            }
    r = requests.post(url,data=data, headers=headers)
    if requests.codes.OK == r.status_code:
        pass
    else:
        pass #TODO: check all images with r.raise_for_status()


def _create_thumbnail_async_handle_results(rpc):
    """ does nothing """
    pass
    #result = rpc.get_result()

def _create_thumbnail_async_callback(rpc):
    """ Use a helper function to define the scope of the callback. """
    """ see: https://cloud.google.com/appengine/docs/python/urlfetch/asynchronousrequests#make_fetch_call"""
    return lambda: _create_thumbnail_async_handle_results(rpc)

class ThumbnailGAEasync(Thumbnail):
    """makes Thumbnail work with GAE, extends flask.thumbnail"""
    _gs_bucket = None
    def __init__(self, app=None):
        super(self.__class__, self).__init__(app)
        self._rpcs = []

    # check if thumbnail already exists
    def _thumb_exists(self, thumb_url):
        #return False
        # TODO: use fast! and google intern file check
        if(len(thumb_url)>5):
            scheme = thumb_url[:5]
            if scheme in ["http:","https"]:
                return self._url_exists(thumb_url)
            else :
                return self._gcs_file_exists(thumb_url)
        return False


    def _url_exists(self, url):
        ## google api compatible
        #from google.appengine.api import urlfetch
        #result = urlfetch.fetch(url)
        #if result.status_code == 200:
        #    return True

        ## requests (faster than urlfetch?)
        try:
            r = requests.head(url)
            if requests.codes.OK == r.status_code: # this url repsonse is OK
                return True
        except Exception as e:
            logging.error("EXEPTION: flask.thumbnailsGAE._url_exists: error {}".format(str(e)))
        return False

    # it's rather slow, but quite safe
    def _gcs_file_exists(self, url):
        try:
            from furl import furl
            from os import path
            thumb_gs_path = self._gs_path(url)
            stat = gcs.stat(thumb_gs_path)
            if stat.filename == thumb_gs_path:
                if stat.st_size > 0:
                    f = furl(url)
                    if stat.content_type.startswith("image/"):
                        import mimetypes
                        if mimetypes.guess_type(url) == stat.content_type:
                            return True
            return False
        except gcs.NotFoundError as e:
            logging.debug("flask.thumbnailsGAE._gcs_file_exists: url: '{}' not found\nException: {}".format(url, str(e)))
            return False
        logging.debug("flask.thumbnailsGAE._gcs_file_exists: url: '{}' return false".format(url))
        return False

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
        return thumb_url

    def _check_and_create(self, thumb_url, img_path, size, crop, bg, quality):
        """ makes async calls to create this thumbnails """
        # TODO: do without const
        if self.app.config["LOCAL"] is True:
            hostname = "http://localhost:8080"
        else:
            hostname = "http://wwwjoeschroecker-pydev.appspot.com"

        crop = crop or None
        bg = bg or None
        quality = quality if quality else 100
        thumb_name = thumb_url.split("/")[-1:][0]

        url = "/".join(("/storethumb/img", thumb_name))

        data = { "thumb_url": thumb_url, "img_path":img_path, "size":size, "crop":crop, "bg":bg, "quality":quality }
        ## headers contains the necessary Content-Type and Content-Length
        ## datagen is a generator object that yields the encoded parameters
        ## possibly read image and send directly?
        #from poster.encode import multipart_encode
        #datagen, headers = multipart_encode({"image1": open("DSC0001.jpg", "rb")})

        #TODO: use app engine moduls:
        #see: https://cloud.google.com/appengine/docs/python/modules/#Python_Background_threads
        #see: https://cloud.google.com/appengine/docs/python/modules/converting
        ### GAE Deferred (not possible, because can't pickle, maybe simpler storage method)
        import json
        from google.appengine.ext import deferred
        ## e.g. self.create_thumbnail(data['thumb_url'], data['img_path'], data['size'], data['crop'], data['bg'], data['quality'])
        deferred.defer(post_data, "".join((hostname,url)) , data)
        # ENABLE DEBUG post_data("".join((hostname,url)), data)
        ## GAE Taskque ##
        #import json
        #data = json.dumps(data)

        ## use class Task()
        #from google.appengine.api.taskqueue import Task
        ## better using class Task.add_async
        #task = Task( url=url
        #             , params={'thumbname': thumb_name} # adds ?paramname=value
        #             , payload=data
        #             , headers={
        #                  "content-type":"application/json"
        #                , "datatype":"json"
        #                }
        #             , method="PUT"
        #             )
        #task.add_async()

        ## use taskqueue.add
        #from google.appengine.api import taskqueue
        #taskqueue.add( url=url
        #             #, params={'thumbname': thumb_name}
        #             , payload=data
        #             , headers={
        #                  "content-type":"application/json"
        #                , "datatype":"json"
        #                }
        #             , method="PUT"
        #             )

        ## RPC Style (still seems slow because of unhandled waits)##
        #url = "/".join((hostname, "storethumb", thumb_name))
        #rpc = urlfetch.create_rpc(deadline=1)
        #rpc.callback = _create_thumbnail_async_callback(rpc) # callback does nothing

        #import json
        #data = json.dumps(data)
        #urlfetch.make_fetch_call(rpc, url
        #                         , payload=data
        #                         , headers={
        #                              "content-type":"application/json"
        #                             , "datatype":"json"
        #                             }
        #                         , method=urlfetch.PUT
        #                        )

        #if self.app.config["LOCAL"] is True:
        #    rpc.wait() # the development server doesn't execute async calls in the background
        #    return
        #else:
        #    self._rpcs.append(rpc)

        return

    #def _clear_rpc_wait(self):
    #    """ clears all waiting rpc, should be call after request received, eg. in create_thumbnail """
    #    for rpc in self._rpcs:
    #        rpc.wait()


    def create_thumbnail(self, thumb_url, img_path, size, crop, bg, quality):
        if self._thumb_exists(thumb_url) is False:
            # get original image and transform to thumbail
            self._create_thumb(thumb_url, img_path, size, crop, bg, quality) # store thumbnail and return url
        return

    def get_serve_url(self, url):
        #TODO: serve "pure" gcs urls, see: http://stackoverflow.com/questions/22174903/how-to-serve-cloudstorage-files-using-app-engine-sdk
        gs_filepath = self._gs_path(url)
        # get_serving_url method => very slow
        # blob_key = blobstore.create_gs_key("/gs" + gs_filepath)
        # return gimages.get_serving_url(blob_key)

        # TODO: serve better urls instade, served directly from gcs
        # example url: http://storage.googleapis.com/wwwjoeschroecker-pydev.appspot.com/img/frontpage-script_200x200_85.jpg

        #local
        if self.app.config["LOCAL"] is True:
            servingurl = "http://localhost:8080/_ah/gcs"+gs_filepath
        else:
            servingurl = "http://storage.googleapis.com/wwwjoeschroecker-pydev.appspot.com"+url
        return servingurl

    def _gs_path(self, url):
        if self._gs_bucket is None:
            self._gs_bucket = app_identity.get_default_gcs_bucket_name()
            # gs_bucket = os.environ.get('BUCKET_NAME', gs_bucket)
        gs_bucket = self._gs_bucket
        gs_path = "/" + gs_bucket + url
        return gs_path

    def _build_thumbnail_url(self, img_url,*args):
        #TODO: maybe build url for blobstore image transformations
        #      see: https://cloud.google.com/appengine/docs/python/images/#Python_Transforming_images_from_the_Blobstore
        return super(ThumbnailGAEasync, self)._build_thumbnail_url(img_url, *args)

