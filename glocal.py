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

class GLocal(GeoAlgorithm):

    INPUT = 'INPUT'
    FIELD = 'FIELD'
    OUTPUT = 'OUTPUT'
    CONTIGUITY = 'CONTIGUITY'
    P_SIM = 'P_SIM'

    def defineCharacteristics(self):
        self.name = "Local Getis-Ord"
        self.group = 'Exploratory Spatial Data Analysis'

        ##input=vector
        ##field=field input
        ##contiguity=string queen
        ##morans_output=output vector
        ##p_sim=output string

        self.addParameter(ParameterVector(self.INPUT,
            self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterTableField(self.FIELD,
            self.tr('Field'), self.INPUT))
        self.addParameter(ParameterSelection(self.CONTIGUITY,
            self.tr('Contiguity'), ["queen","rook"]))

        self.addOutput(OutputVector(self.OUTPUT, self.tr('Result')))
        self.addOutput(OutputString(self.P_SIM, self.tr('p_sim')))

    def processAlgorithm(self, progress):

        field = self.getParameterValue(self.FIELD)
        field = field[0:10] # try to handle Shapefile field length limit
        filename = self.getParameterValue(self.INPUT)
        layer = dataobjects.getObjectFromUri(filename)
        filename = dataobjects.exportVectorLayer(layer)
        provider = layer.dataProvider()
        fields = provider.fields()
        fields.append(QgsField('L_G', QVariant.Double))
        fields.append(QgsField('L_G_p', QVariant.Double))
        fields.append(QgsField('L_G_S', QVariant.Double))
        fields.append(QgsField('L_G_ll_hh', QVariant.Double))

        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            fields, provider.geometryType(), layer.crs() )


        contiguity = self.getParameterValue(self.CONTIGUITY)
        if contiguity == 'queen':
            print 'INFO: Local Getis-Ord G using queen contiguity'
            w=pysal.queen_from_shapefile(filename)
        else:
            print 'INFO: Local Getis-Ord G using rook contiguity'
            w=pysal.rook_from_shapefile(filename)

        f = pysal.open(filename.replace('.shp','.dbf'))
        y=np.array(f.by_col[str(field)])
        lg = pysal.G_Local(y, w, transform="b", permutations=999)

        # http://pysal.readthedocs.org/en/latest/library/esda/moran.html?highlight=local%20moran#pysal.esda.moran.Moran_Local
        # values indicate quadrat location 1 HH,  2 LH,  3 LL,  4 HL

        # http://www.biomedware.com/files/documentation/spacestat/Statistics/LM/Results/Interpreting_univariate_Local_Moran_statistics.htm
        # category - scatter plot quadrant - autocorrelation - interpretation
        # high-high - upper right (red) - positive - Cluster - "I'm high and my neighbors are high."
        # high-low - lower right (pink) - negative - Outlier - "I'm a high outlier among low neighbors."
        # low-low - lower left (med. blue) - positive - Cluster - "I'm low and my neighbors are low."
        # low-high - upper left (light blue) - negative - Outlier - "I'm a low outlier among high neighbors."

        # http://help.arcgis.com/en/arcgisdesktop/10.0/help/index.html#/What_is_a_z_score_What_is_a_p_value/005p00000006000000/
        # z-score (Standard Deviations) | p-value (Probability) | Confidence level
        #     < -1.65 or > +1.65        |        < 0.10         |       90%
        #     < -1.96 or > +1.96        |        < 0.05         |       95%
        #     < -2.58 or > +2.58        |        < 0.01         |       99%

        self.setOutputValue(self.P_SIM, str(lg.p_sim))

        sig_g = 1.0 * lg.p_sim <= 0.01  # could make significance level an option
        ll_hh = 1.0 * (lg.Gs > lg.EGs) + 1
        sig_ll_hh = sig_g * ll_hh

        outFeat = QgsFeature()
        i = 0
        for inFeat in processing.features(layer):
            inGeom = inFeat.geometry()
            outFeat.setGeometry(inGeom)
            attrs = inFeat.attributes()
            attrs.append(float(lg.Gs[i]))
            attrs.append(float(lg.p_sim[i]))
            attrs.append(float(sig_g[i]))
            attrs.append(float(sig_ll_hh[i]))
            outFeat.setAttributes(attrs)
            writer.addFeature(outFeat)
            i += 1

        del writer

        out_layer = dataobjects.getObjectFromUri(self.getOutputValue(
         self.OUTPUT))

        #out_layer = dataobjects.getObjectFromName("Result")

        #layer = self.getOutputFromName(self.OUTPUT)
        #output_layer = OutputVector(self.OUTPUT, self.tr('Result'))
        classes = [0, 1, 2]
        labels = ["not. sig", "LL", "HH"]
        colors = ["#FFFFFF", "#000099", "#CC0000"]

        quads = {}
        for i in classes:
            quads[i] = (colors[i], labels[i])

        categories = []
        for quad, (color, label) in quads.items():
            symbol = QgsSymbolV2.defaultSymbol(out_layer.geometryType())
            symbol.setColor(QtGui.QColor(color))
            category = QgsRendererCategoryV2(quad, symbol, label)
            categories.append(category)

        expression = "L_G_ll_hh"
        renderer = QgsCategorizedSymbolRendererV2(expression,
                                                  categories)
        out_layer.setRendererV2(renderer)
        QgsMapLayerRegistry.instance().addMapLayer(out_layer)
        iface.mapCanvas().refresh()
        iface.legendInterface().refreshLayerSymbology(out_layer)
        iface.mapCanvas().refresh()