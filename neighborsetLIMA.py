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

class NeighborSetLIMA(GeoAlgorithm):

    INPUT = 'INPUT'
    YEAR1 = 'YEAR1'
    YEAR2 = 'YEAR2'
    OUTPUT = 'OUTPUT'
    REGIME = 'REGIME'
    P_SIM = 'P_SIM'

    def defineCharacteristics(self):
        self.name = "Neighbor Set LIMA"
        self.group = 'Spatial Dynamics'

        ##input=vector
        ##field=field input
        ##contiguity=string queen
        ##morans_output=output vector
        ##p_sim=output string 

        self.addParameter(ParameterVector(self.INPUT,
            self.tr('Input layer'), [ParameterVector.VECTOR_TYPE_POLYGON]))
        self.addParameter(ParameterTableField(self.YEAR1,
            self.tr('Year1'), self.INPUT))
        self.addParameter(ParameterTableField(self.YEAR2,
                                              self.tr('Year2'),
                                              self.INPUT))
        self.addParameter(ParameterTableField(self.REGIME,
                                              self.tr('Regime'),
                                              self.INPUT))
        self.addOutput(OutputVector(self.OUTPUT, self.tr('Result')))
        self.addOutput(OutputString(self.P_SIM, self.tr('p_sim')))

    def processAlgorithm(self, progress):

        year1 = self.getParameterValue(self.YEAR1)
        year1 = year1[0:10] # try to handle Shapefile field length limit

        year2 = self.getParameterValue(self.YEAR2)
        year2 = year2[0:10]

        regime = self.getParameterValue(self.REGIME)
        regime = regime[0:10]

        filename = self.getParameterValue(self.INPUT)
        layer = dataobjects.getObjectFromUri(filename)
        filename = dataobjects.exportVectorLayer(layer)        
        provider = layer.dataProvider()
        fields = provider.fields()
        fields.append(QgsField('Tau_LN', QVariant.Double))
        fields.append(QgsField('Tau_LN_P', QVariant.Double))
        fields.append(QgsField('Tau_LN_Sign', QVariant.Int))
        fields.append(QgsField('Tau_LN_C', QVariant.Int))


        writer = self.getOutputFromName(self.OUTPUT).getVectorWriter(
            fields, provider.geometryType(), layer.crs() )


        f = pysal.open(filename.replace('.shp','.dbf'))
        y1=np.array(f.by_col[str(year1)])
        y2 = np.array(f.by_col[str(year2)])
        r = np.array(f.by_col[str(regime)])
        w = pysal.weights.block_weights(r)

        np.random.seed(123456)
        lm = pysal.spatial_dynamics.rank\
                .Tau_Local_Neighbor_DecomFromSpatialTau(y1,y2,w,
                                                        permutations
                                                        = 999)

        print "Neighbor Set LIMA"
        print "Year1: ", year1
        print "Year2: ", year2
        print "Regime:  ", regime
        print "Neighbor Set LIMA Values: ", lm.tau_ln
        print "p-value: ", lm.tau_ln_pvalues
        print "Concordance:", lm.sign

        self.setOutputValue(self.P_SIM, str(lm.tau_ln_pvalues))

        sig_tau_ln = lm.sign * (lm.tau_ln_pvalues <= 0.05)
        outFeat = QgsFeature()
        i = 0
        for inFeat in processing.features(layer):
            inGeom = inFeat.geometry()
            outFeat.setGeometry(inGeom)
            attrs = inFeat.attributes()
            attrs.append(float(lm.tau_ln[i]))
            attrs.append(float(lm.tau_ln_pvalues[i]))
            attrs.append(int(lm.sign[i]))
            attrs.append(int(sig_tau_ln[i]))
            outFeat.setAttributes(attrs)
            writer.addFeature(outFeat)
            i+=1

        del writer

        out_layer = dataobjects.getObjectFromUri(self.getOutputValue(
         self.OUTPUT))

        #out_layer = dataobjects.getObjectFromName("Result")

        #layer = self.getOutputFromName(self.OUTPUT)
        #output_layer = OutputVector(self.OUTPUT, self.tr('Result'))
        classes = [0, 1, -1]
        labels = ["not. sig", "Concordance", "Discordance"]
        colors = ["#FFFFFF", "#CC0000", "#000099"]

        quads = {}
        for i in classes:
            quads[i] = (colors[i], labels[i])

        categories = []
        for quad, (color, label) in quads.items():
            symbol = QgsSymbolV2.defaultSymbol(out_layer.geometryType())
            symbol.setColor(QtGui.QColor(color))
            category = QgsRendererCategoryV2(quad, symbol, label)
            categories.append(category)

        expression = "Tau_LN_C"
        renderer = QgsCategorizedSymbolRendererV2(expression,
                                                  categories)
        out_layer.setRendererV2(renderer)
        QgsMapLayerRegistry.instance().addMapLayer(out_layer)
        iface.mapCanvas().refresh()
        iface.legendInterface().refreshLayerSymbology(out_layer)
        iface.mapCanvas().refresh()


