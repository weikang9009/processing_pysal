import pysal 
import numpy as np
import processing 
from processing.tools.vector import VectorWriter
from qgis.core import *
from PyQt4.QtCore import *
from processing.core.GeoAlgorithm import GeoAlgorithm
from processing.core.parameters import *
from processing.core.outputs import *
from processing.tools import dataobjects
from PyQt4 import QtGui
from qgis.utils import iface

class TheilDSim(GeoAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    REGIME = 'REGIME'

    def defineCharacteristics(self):
        self.name = "Theil Interregional Inequality Decomposition"
        self.group = 'Inequality'

        self.addParameter(ParameterVector(self.INPUT,
            self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterTableField(self.FIELD,
            self.tr('Field'), self.INPUT))
        self.addParameter(ParameterTableField(self.REGIME,
                                              self.tr('Regime'),
                                              self.INPUT))
        
    def processAlgorithm(self, progress):
        field = self.getParameterValue(self.FIELD)
        field = field[0:10] # try to handle Shapefile field length limit

        regime = self.getParameterValue(self.REGIME)
        regime = regime[0:10]  # try to handle Shapefile field length limit

        filename = self.getParameterValue(self.INPUT)
        layer = dataobjects.getObjectFromUri(filename)
        filename = dataobjects.exportVectorLayer(layer)

        f = pysal.open(filename.replace('.shp','.dbf'))

        y=np.array(f.by_col[str(field)])
        r = np.array(f.by_col[str(regime)])

        theil_d = pysal.TheilDSim(y, r, 999)


        print "Theil Interregional Inequality Decomposition"
        print "Attribute: ", field
        print "Regime:  ", regime
        print "Global inequality T: ", theil_d.T
        print "Within regions: ", theil_d.wg[0][0]
        print "Between regions: ", theil_d.bg[0][0]
        print "p-value: ", theil_d.bg_pvalue[0]

        # render the map based on regionalization
        classes = np.unique(r)
        labels = []
        for r_i in classes:
            l_name = "Region " + str(int(r_i))
            labels.append(l_name)
        colors = ["#a6cee3", "#1f78b4", "#b2df8a", "#33a02c",
                  "#fb9a99","#e31a1c", "#fdbf6f", "#ff7f00",
                  "#cab2d6","#6a3d9a", "#ffff99", "#b15928"]

        quads = {}
        for i in range(len(classes)):
            quads[int(classes[i])] = (colors[i], labels[i])

        categories = []
        for quad, (color, label) in quads.items():
            symbol = QgsSymbolV2.defaultSymbol(layer.geometryType())
            symbol.setColor(QtGui.QColor(color))
            category = QgsRendererCategoryV2(quad, symbol, label)
            categories.append(category)

        expression = regime
        renderer = QgsCategorizedSymbolRendererV2(expression,
                                                  categories)
        layer.setRendererV2(renderer)
        QgsMapLayerRegistry.instance().addMapLayer(layer)
        iface.mapCanvas().refresh()
        iface.legendInterface().refreshLayerSymbology(layer)
        iface.mapCanvas().refresh()
        layer.triggerRepaint()



