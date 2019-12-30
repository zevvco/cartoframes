from ..widget import Widget


def animation_widget(title='', description='', footer='', prop=''):
    """Helper function for quickly creating an animated widget.

    The animation widget includes an animation status bar as well as controls to play or pause animated data.
    The `filter` property of your map's style, applied to either a date or numeric field, drives both
    the animation and the widget. Only **one** animation can be controlled per layer.

    To learn more about creating animations visit:
      - https://carto.com/developers/carto-vl/guides/animated-visualizations.

    Args:
        title (str, optional): Title of widget.
        description (str, optional): Description text widget placed under widget title.
        footer (str, optional): Footer text placed on the widget bottom.
        prop (str, optional): Property of the style to get the animation. Default "filter".

    Returns:
        cartoframes.viz.widget.Widget

    Example:
        >>> animation_widget(
        ...     title='Widget title',
        ...     description='Widget description',
        ...     footer='Widget footer')

    """
    return Widget('animation', None, title, description, footer,
                  prop=prop)
