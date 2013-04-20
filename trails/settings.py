# String to use for user_unicode when user is None.
TRAILS_USER_NONE = u'(none)'

# Record trails when request.user is None or not set (usually happens as a
# result of management commands or background tasks)?
TRAILS_LOG_USER_NONE = False

# String to use for user_unicode when user.is_anonymous().
TRAILS_USER_ANONYMOUS = u'(anonymous)'

# Record trails when request.user is the anonymous user?
TRAILS_LOG_USER_ANONYMOUS = True

# List of strings specifying app_label or app_label.ModelName to exclude.
TRAILS_EXCLUDE = []

# Record trails to the database?
TRAILS_USE_DATABASE = True

# Record trails to the Python logging module?
TRAILS_USE_LOGGING = False

# Logger name to use for the Python logging module.
TRAILS_LOGGER = 'trails'

# Replace default admin history view with trails history view?
TRAILS_ADMIN_HISTORY = False
