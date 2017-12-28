"""carto magics"""
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)
from cartoframes.context import CartoContext
from cartoframes import utils
# GOALS
# - have it automatically find a CartoContext object
# - make it agnostic to line or cell magics
# - maps!

@magics_class
class CartoMagics(Magics):
    """Magics for bringing CARTO exploratory data analysis to IPython"""

    def find_carto_context(self, context):
        if context is None:
            # try to find a CartoContext instance if not specified
            for key, val in self.shell.user_ns.items():
                if isinstance(val, CartoContext):
                    context = key
                    break
        if context is None:
            raise ValueError('No CartoContext found or specified')
        return context

    @line_cell_magic
    def cartoquery(self, line, cell=None):
        "query carto"
        opts, table = self.parse_options(line, 'c:', posix=False, strict=False)
        if cell:
            query = cell
        else:
            query = 'select * from {}'.format(table)

        context = opts.get('c', None)
        # try to find a CartoContext instance if not specified
        context = self.find_carto_context(context)

        evalstr = "{0}.query(\'{1}\')".format(context, query.replace('\n', ' '))
        return eval(evalstr, self.shell.user_ns)

    @line_cell_magic
    def cartomap(self, line, cell=None):
        """carto map"""
        opts, table = self.parse_options(line, 'c:s:ivt:',
                                         posix=False, strict=False)
        context = opts.get('c', None)
        stylecol = opts.get('s', None)
        timecol = opts.get('t', None)
        interactive = True if 'i' in opts else False

        # try to find a CartoContext instance if not specified
        context = self.find_carto_context(context)

        if stylecol is not None:
            stylecol = utils.pgquote(stylecol)

        if timecol is not None:
            timecol = utils.pgquote(timecol)

        if cell:
            layer = 'cartoframes.QueryLayer({query}, color={color}, time={time})'.format(
                query=utils.pgquote(cell.replace('\n', ' ')),
                color=stylecol,
                time=timecol)
        else:
            layer = 'cartoframes.Layer({table}, color={color}, time={time})'.format(
                table=utils.pgquote(table),
                color=stylecol,
                time=timecol)
        evalstr = "{0}.map({1},interactive={2})".format(context,
                                                         layer,
                                                         interactive)
        if 'v' in opts:
            print(evalstr)

        return eval(evalstr, self.shell.user_ns)

ipython_sess = get_ipython()
ipython_sess.register_magics(CartoMagics)
